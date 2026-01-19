"""Chess.com data adapter for cheater game ingestion.

Integrates with:
1. Chess.com public API for player status checks
2. Archive.org historical cheater lists
3. Existing ChessGuard discover_cheaters.py patterns
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, List, Optional, Dict, Any, Set

import httpx

from .base import PlatformAdapter, RawGame
from ..models import CheaterLabel

LOGGER = logging.getLogger(__name__)

# Rate limits (Chess.com is more restrictive)
CHESSCOM_API_DELAY = 0.5  # Conservative: 2 requests per second


class ChessComAdapter(PlatformAdapter):
    """Adapter for Chess.com data ingestion.
    
    Discovers cheaters by checking account status for 'closed:fair_play_violations'.
    """
    
    source_name = "chesscom"
    
    def __init__(self):
        """Initialize Chess.com adapter."""
        super().__init__()
        self.base_url = "https://api.chess.com/pub"
    
    async def get_titled_players(self, title: str) -> List[str]:
        """Fetch list of usernames for a given title (GM, IM, etc)."""
        url = f"{self.base_url}/titled/{title}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json().get("players", [])
                LOGGER.warning(f"Failed to fetch {title} players: {resp.status_code}")
        except Exception as e:
            LOGGER.error(f"Error fetching {title} players: {e}")
        return []

    async def fetch_games(
        self, 
        limit: int = 1000, 
        username: Optional[str] = None,
        usernames: Optional[List[str]] = None,
        months: int = 3,
        **kwargs
    ) -> AsyncIterator[RawGame]:
        """Fetch games for specified user(s).
        
        Args:
            limit: Max games per user
            username: Single username to fetch
            usernames: List of usernames to fetch
            months: Number of months of history to fetch
        """
        if username:
            usernames = [username]
        
        if not usernames:
            LOGGER.warning("No usernames provided to fetch_games")
            return
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for user in usernames:
                games_fetched = 0
                async for game in self._fetch_user_games(client, user, limit, months):
                    yield game
                    games_fetched += 1
                    if games_fetched >= limit:
                        break
                
                LOGGER.info(f"Fetched {games_fetched} games for {user}")
                await asyncio.sleep(CHESSCOM_API_DELAY)
    
    async def _fetch_user_games(
        self, 
        client: httpx.AsyncClient, 
        username: str,
        limit: int,
        months: int
    ) -> AsyncIterator[RawGame]:
        """Fetch games for a single user from their archives."""
        # Get list of monthly archives
        archives_url = f"{self.base_url}/player/{username.lower()}/games/archives"
        
        try:
            response = await client.get(archives_url, headers=self.headers)
            if response.status_code == 404:
                LOGGER.warning(f"User not found: {username}")
                return
            
            if response.status_code != 200:
                LOGGER.warning(f"Failed to get archives for {username}: {response.status_code}")
                return
            
            archives = response.json().get("archives", [])
            
            # Get most recent months
            recent_archives = archives[-months:] if len(archives) > months else archives
            
            games_yielded = 0
            for archive_url in reversed(recent_archives):
                if games_yielded >= limit:
                    break
                
                await asyncio.sleep(CHESSCOM_API_DELAY)
                
                try:
                    response = await client.get(archive_url, headers=self.headers)
                    if response.status_code != 200:
                        continue
                    
                    games = response.json().get("games", [])
                    
                    for game_data in reversed(games):
                        if games_yielded >= limit:
                            break
                        
                        yield self._to_raw_game(game_data, username)
                        games_yielded += 1
                        
                except Exception as e:
                    LOGGER.warning(f"Error fetching archive {archive_url}: {e}")
                    continue
                    
        except Exception as e:
            LOGGER.error(f"Error fetching games for {username}: {e}")
    
    def _to_raw_game(self, data: Dict[str, Any], cheater_username: str) -> RawGame:
        """Convert Chess.com API game to RawGame."""
        white = data.get("white", {})
        black = data.get("black", {})
        
        white_name = white.get("username", "")
        black_name = black.get("username", "")
        
        # Determine which side is the cheater
        cheater_side = "none"
        if white_name.lower() == cheater_username.lower():
            cheater_side = "white"
        elif black_name.lower() == cheater_username.lower():
            cheater_side = "black"
        
        # Get PGN
        pgn = data.get("pgn", "")
        
        return RawGame(
            source_id=data.get("uuid", data.get("url", "").split("/")[-1]),
            pgn=pgn,
            white_username=white_name,
            black_username=black_name,
            white_rating=white.get("rating"),
            black_rating=black.get("rating"),
            time_control=data.get("time_control"),
            time_class=data.get("time_class", "blitz"),
            game_date=self._parse_timestamp(data.get("end_time")),
            result=self._parse_result(white.get("result"), black.get("result")),
            metadata={
                "cheater_username": cheater_username,
                "cheater_side": cheater_side,
                "url": data.get("url"),
                "rated": data.get("rated", True),
                "rules": data.get("rules"),
                "accuracies": data.get("accuracies"),
            }
        )
    
    def get_cheater_label(self, raw: RawGame) -> CheaterLabel:
        """Determine label based on which side is the known cheater."""
        cheater_side = raw.metadata.get("cheater_side", "none") if raw.metadata else "none"
        
        return CheaterLabel(
            side=cheater_side,
            cheater_type="unknown",
            confirmed=True,  # Account was closed by Chess.com
        )
    
    async def discover_cheaters(self, limit: int = 100) -> List[str]:
        """Discover cheaters using BFS crawl from seed players.
        
        Checks account status for 'closed:fair_play_violations'.
        """
        discovered = []
        seed_players = [
            "hikaru", "gothamchess", "danielnaroditsky", "magnuscarlsen",
            "botez", "annacramling", "ericrosen", "akanemsko"
        ]
        
        visited: Set[str] = set()
        queue = list(seed_players)
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            while queue and len(discovered) < limit:
                username = queue.pop(0)
                if username.lower() in visited:
                    continue
                
                visited.add(username.lower())
                
                # Get user's opponents
                opponents = await self._get_recent_opponents(client, username)
                
                # Check each opponent
                for opponent in opponents:
                    if opponent.lower() in visited:
                        continue
                    
                    is_cheater, status = await self._check_user_status(client, opponent)
                    if is_cheater:
                        discovered.append(opponent)
                        LOGGER.info(f"Discovered cheater: {opponent} ({status})")
                    else:
                        queue.append(opponent)
                    
                    await asyncio.sleep(CHESSCOM_API_DELAY)
                
                # Limit queue growth
                if len(queue) > 500:
                    queue = queue[:500]
        
        return discovered
    
    async def _get_recent_opponents(
        self, 
        client: httpx.AsyncClient, 
        username: str,
        limit: int = 20
    ) -> List[str]:
        """Get recent opponents of a player."""
        opponents = []
        archives_url = f"{self.base_url}/player/{username.lower()}/games/archives"
        
        try:
            response = await client.get(archives_url, headers=self.headers)
            if response.status_code != 200:
                return []
            
            archives = response.json().get("archives", [])
            if not archives:
                return []
            
            # Get most recent archive
            await asyncio.sleep(CHESSCOM_API_DELAY)
            response = await client.get(archives[-1], headers=self.headers)
            
            if response.status_code != 200:
                return []
            
            games = response.json().get("games", [])
            
            for game in games[-limit:]:
                white = game.get("white", {}).get("username", "")
                black = game.get("black", {}).get("username", "")
                
                if white.lower() != username.lower() and white:
                    opponents.append(white)
                if black.lower() != username.lower() and black:
                    opponents.append(black)
                    
        except Exception as e:
            LOGGER.warning(f"Error getting opponents for {username}: {e}")
        
        return list(set(opponents))
    
    async def _check_user_status(
        self, 
        client: httpx.AsyncClient, 
        username: str
    ) -> tuple[bool, str]:
        """Check if a user account is closed for fair play violations."""
        url = f"{self.base_url}/player/{username.lower()}"
        
        try:
            response = await client.get(url, headers=self.headers)
            if response.status_code == 404:
                return False, ""
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "")
                
                # Check for fair play violation
                if "fair_play" in status.lower() or status == "closed:fair_play_violations":
                    return True, status
                
        except Exception as e:
            LOGGER.warning(f"Error checking status for {username}: {e}")
        
        return False, ""
    
    async def load_known_cheaters(self, cheaters_file: Path) -> List[str]:
        """Load known cheaters from existing ChessGuard database.
        
        Args:
            cheaters_file: Path to known_cheaters.json
            
        Returns:
            List of Chess.com usernames
        """
        if not cheaters_file.exists():
            return []
        
        with open(cheaters_file, "r") as f:
            data = json.load(f)
        
        return [
            c["username"] 
            for c in data.get("titled_cheaters", [])
            if c.get("platform") == "chesscom"
        ]
    
    @staticmethod
    def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
        """Parse Unix timestamp to datetime."""
        if not ts:
            return None
        return datetime.fromtimestamp(ts)
    
    @staticmethod
    def _parse_result(white_result: Optional[str], black_result: Optional[str]) -> str:
        """Convert Chess.com result to standard format."""
        if white_result == "win":
            return "1-0"
        elif black_result == "win":
            return "0-1"
        elif white_result in ("draw", "stalemate", "agreed", "repetition", "insufficient"):
            return "1/2-1/2"
        return "*"
