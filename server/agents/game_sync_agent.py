"""Automated Game Sync Agent.

Scheduled agent that fetches new games from connected accounts,
runs analysis, and flags suspicious opponents.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from collections import defaultdict

import httpx
from sqlalchemy.orm import Session

from .models import ConnectedAccount, SyncJob, CheatReport, Platform

LOGGER = logging.getLogger(__name__)

# Rate limits
LICHESS_DELAY = 0.5
CHESSCOM_DELAY = 0.5


class GameSyncAgent:
    """Agent that syncs games from connected accounts and flags cheaters."""
    
    def __init__(self, session: Session):
        self.session = session
        self.headers = {"User-Agent": "ChessGuard/1.0 (research@chessguard.dev)"}
    
    async def sync_account(self, account: ConnectedAccount) -> SyncJob:
        """Sync games for a single connected account.
        
        Args:
            account: Connected account to sync
            
        Returns:
            SyncJob with results
        """
        job = SyncJob(
            account_id=account.id,
            status="running",
            started_at=datetime.utcnow()
        )
        self.session.add(job)
        self.session.commit()
        
        try:
            # Fetch new games
            games = await self._fetch_games(account)
            job.games_fetched = len(games)
            
            # Group games by opponent
            opponents = self._group_by_opponent(games, account.platform_username)
            job.opponents_checked = len(opponents)
            
            # Analyze each opponent
            flagged = await self._analyze_opponents(account.user_id, opponents, account.platform)
            job.opponents_flagged = len(flagged)
            job.games_analyzed = sum(len(g) for g in opponents.values())
            
            # Update sync status
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            account.last_synced_at = datetime.utcnow()
            
            if games:
                # Update last game timestamp for incremental sync
                latest_game = max(games, key=lambda g: g.get("timestamp", 0))
                if "timestamp" in latest_game:
                    account.last_game_timestamp = datetime.fromtimestamp(latest_game["timestamp"])
            
            LOGGER.info(
                f"Sync completed for {account.platform_username}: "
                f"{job.games_fetched} games, {job.opponents_flagged} flagged"
            )
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            LOGGER.error(f"Sync failed for {account.platform_username}: {e}")
        
        self.session.commit()
        return job
    
    async def sync_all_enabled(self) -> List[SyncJob]:
        """Sync all enabled connected accounts.
        
        Returns:
            List of completed SyncJobs
        """
        accounts = self.session.query(ConnectedAccount).filter_by(
            sync_enabled=True
        ).all()
        
        LOGGER.info(f"Starting sync for {len(accounts)} accounts")
        
        jobs = []
        for account in accounts:
            job = await self.sync_account(account)
            jobs.append(job)
            
            # Delay between accounts to respect rate limits
            await asyncio.sleep(1)
        
        return jobs
    
    async def _fetch_games(
        self, 
        account: ConnectedAccount,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch games from the platform API.
        
        Uses incremental sync if last_game_timestamp is set.
        """
        games = []
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            if account.platform == Platform.LICHESS.value:
                games = await self._fetch_lichess_games(client, account, limit)
            elif account.platform == Platform.CHESSCOM.value:
                games = await self._fetch_chesscom_games(client, account, limit)
        
        return games
    
    async def _fetch_lichess_games(
        self,
        client: httpx.AsyncClient,
        account: ConnectedAccount,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch games from Lichess API."""
        games = []
        url = f"https://lichess.org/api/games/user/{account.platform_username}"
        
        headers = {**self.headers, "Accept": "application/x-ndjson"}
        if account.access_token:
            headers["Authorization"] = f"Bearer {account.access_token}"
        
        params = {"max": limit, "pgnInJson": "true", "clocks": "true"}
        
        # Incremental sync: only fetch games newer than last sync
        if account.last_game_timestamp:
            params["since"] = int(account.last_game_timestamp.timestamp() * 1000)
        
        try:
            async with client.stream("GET", url, headers=headers, params=params) as response:
                if response.status_code != 200:
                    LOGGER.warning(f"Lichess API error: {response.status_code}")
                    return []
                
                import json
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            game = json.loads(line)
                            game["timestamp"] = game.get("createdAt", 0) / 1000
                            games.append(game)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            LOGGER.error(f"Error fetching Lichess games: {e}")
        
        return games
    
    async def _fetch_chesscom_games(
        self,
        client: httpx.AsyncClient,
        account: ConnectedAccount,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch games from Chess.com API."""
        games = []
        
        # Get archives
        archives_url = f"https://api.chess.com/pub/player/{account.platform_username.lower()}/games/archives"
        
        try:
            response = await client.get(archives_url, headers=self.headers)
            if response.status_code != 200:
                return []
            
            archives = response.json().get("archives", [])
            
            # Get most recent archives
            for archive_url in reversed(archives[-2:]):
                if len(games) >= limit:
                    break
                
                await asyncio.sleep(CHESSCOM_DELAY)
                response = await client.get(archive_url, headers=self.headers)
                
                if response.status_code == 200:
                    archive_games = response.json().get("games", [])
                    
                    for game in reversed(archive_games):
                        # Skip games older than last sync
                        if account.last_game_timestamp:
                            game_time = game.get("end_time", 0)
                            if game_time and game_time < account.last_game_timestamp.timestamp():
                                continue
                        
                        game["timestamp"] = game.get("end_time", 0)
                        games.append(game)
                        
                        if len(games) >= limit:
                            break
                            
        except Exception as e:
            LOGGER.error(f"Error fetching Chess.com games: {e}")
        
        return games
    
    def _group_by_opponent(
        self, 
        games: List[Dict[str, Any]], 
        own_username: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group games by opponent username."""
        opponents = defaultdict(list)
        
        for game in games:
            # Lichess format
            if "players" in game:
                white = game["players"].get("white", {}).get("user", {}).get("name", "")
                black = game["players"].get("black", {}).get("user", {}).get("name", "")
            # Chess.com format
            else:
                white = game.get("white", {}).get("username", "")
                black = game.get("black", {}).get("username", "")
            
            if white.lower() == own_username.lower():
                opponent = black
            else:
                opponent = white
            
            if opponent:
                opponents[opponent].append(game)
        
        return dict(opponents)
    
    async def _analyze_opponents(
        self,
        user_id: int,
        opponents: Dict[str, List[Dict[str, Any]]],
        platform: str
    ) -> List[str]:
        """Analyze opponents and flag suspicious ones.
        
        Returns:
            List of flagged opponent usernames
        """
        flagged = []
        
        for opponent, games in opponents.items():
            if len(games) < 2:
                # Need at least 2 games for meaningful analysis
                continue
            
            # Check if opponent is already in known cheater database
            from server.services.cheater_db import check_player, BanStatus
            status = check_player(opponent, platform)
            
            if status == BanStatus.BANNED:
                # Already known cheater, create report
                await self._create_report(
                    user_id=user_id,
                    opponent=opponent,
                    platform=platform,
                    games=games,
                    is_confirmed=True
                )
                flagged.append(opponent)
                continue
            
            # Run analysis on games
            # This would use the full ensemble pipeline
            # For now, simplified check
            is_suspicious, score, reason = await self._quick_check(games, opponent, platform)
            
            if is_suspicious:
                await self._create_report(
                    user_id=user_id,
                    opponent=opponent,
                    platform=platform,
                    games=games,
                    score=score,
                    reason=reason
                )
                flagged.append(opponent)
        
        return flagged
    
    async def _quick_check(
        self,
        games: List[Dict[str, Any]],
        opponent: str,
        platform: str
    ) -> tuple[bool, int, str]:
        """Check if opponent is suspicious using ML model + heuristics.
        
        Returns:
            Tuple of (is_suspicious, score 0-100, reason)
        """
        from server.services.model_inference import predict_cheating
        
        max_score = 0.0
        reasons = []
        suspicious_games = 0
        
        for game in games:
            # Skip very short games
            pgn = game.get("pgn", "")
            if len(pgn) < 100: 
                continue
                
            prob, reason = predict_cheating(game)
            if prob > max_score:
                max_score = prob
            
            if prob > 0.7:  # High confidence threshold
                suspicious_games += 1
                reasons.append(f"Game vs {game.get('white', {}).get('username', 'start')} ({prob:.0%})")
        
        # Heuristics fallback / boost
        if platform == "chesscom":
            accuracies = []
            for game in games:
                game_acc = game.get("accuracies", {})
                white = game.get("white", {}).get("username", "")
                
                if white.lower() == opponent.lower():
                    if "white" in game_acc:
                        accuracies.append(game_acc["white"])
                elif "black" in game_acc:
                    accuracies.append(game_acc["black"])
            
            if accuracies and len(accuracies) >= 3:
                avg_accuracy = sum(accuracies) / len(accuracies)
                if avg_accuracy > 95:
                    max_score = max(max_score, 0.95)
                    reasons.append(f"Avg Accuracy: {avg_accuracy:.1f}%")
        
        # Final decision
        final_score = int(max_score * 100)
        is_suspicious = final_score >= 80 or (final_score >= 70 and len(reasons) >= 2)
        
        reason_text = " | ".join(reasons[:3]) if reasons else "ML Analysis"
        
        return is_suspicious, final_score, reason_text
    
    async def _create_report(
        self,
        user_id: int,
        opponent: str,
        platform: str,
        games: List[Dict[str, Any]],
        score: int = 100,
        reason: str = "",
        is_confirmed: bool = False
    ):
        """Create a cheat report for a flagged opponent."""
        from .explanation_engine import generate_summary
        
        risk_level = "CRITICAL" if score >= 85 else "HIGH" if score >= 70 else "MODERATE"
        
        if is_confirmed:
            summary = f"{opponent} is a confirmed cheater banned by {platform.title()} for fair play violations."
            risk_level = "CRITICAL"
            score = 100
        else:
            summary = generate_summary(opponent, score, risk_level, reason, len(games))
        
        report = CheatReport(
            user_id=user_id,
            flagged_player=opponent,
            platform=platform,
            ensemble_score=score,
            risk_level=risk_level,
            summary_text=summary,
            games_analyzed=len(games),
        )
        
        self.session.add(report)
        self.session.commit()
        
        LOGGER.info(f"Created report for {opponent}: {risk_level} ({score})")


async def run_scheduled_sync(session: Session):
    """Entry point for scheduled sync (called by scheduler)."""
    agent = GameSyncAgent(session)
    await agent.sync_all_enabled()
