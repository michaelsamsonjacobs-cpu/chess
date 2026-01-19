"""Lichess data adapter for cheater game ingestion.

Integrates with:
1. Lichess API for user status checks (tosViolation flag)
2. database.lichess.org for bulk PGN downloads
3. Existing ChessGuard BFS crawler for cheater discovery
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

# Rate limits
LICHESS_API_DELAY = 0.5  # 2 requests per second for authenticated
LICHESS_GAMES_DELAY = 0.1  # Streaming is more permissive


class LichessAdapter(PlatformAdapter):
    """Adapter for Lichess data ingestion.
    
    Discovers cheaters by checking user status and fetches their games.
    """
    
    source_name = "lichess"
    
    def __init__(self, api_token: Optional[str] = None):
        """Initialize Lichess adapter.
        
        Args:
            api_token: Optional Lichess OAuth token for higher rate limits
        """
        super().__init__(api_key=api_token)
        self.base_url = "https://lichess.org"
        
        if api_token:
            self.headers["Authorization"] = f"Bearer {api_token}"
    
    async def fetch_games(
        self, 
        limit: int = 1000, 
        username: Optional[str] = None,
        usernames: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncIterator[RawGame]:
        """Fetch games for specified user(s).
        
        Args:
            limit: Max games per user
            username: Single username to fetch
            usernames: List of usernames to fetch
        """
        if username:
            usernames = [username]
        
        if not usernames:
            LOGGER.warning("No usernames provided to fetch_games")
            return
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for user in usernames:
                games_fetched = 0
                async for game in self._fetch_user_games(client, user, limit):
                    yield game
                    games_fetched += 1
                
                LOGGER.info(f"Fetched {games_fetched} games for {user}")
                await asyncio.sleep(LICHESS_API_DELAY)
    
    async def _fetch_user_games(
        self, 
        client: httpx.AsyncClient, 
        username: str,
        limit: int
    ) -> AsyncIterator[RawGame]:
        """Fetch games for a single user using streaming API."""
        url = f"{self.base_url}/api/games/user/{username}"
        params = {
            "max": limit,
            "pgnInJson": "true",
            "clocks": "true",
            "evals": "false",
            "opening": "true",
        }
        
        try:
            async with client.stream(
                "GET", 
                url, 
                headers={**self.headers, "Accept": "application/x-ndjson"},
                params=params
            ) as response:
                if response.status_code == 404:
                    LOGGER.warning(f"User not found: {username}")
                    return
                
                if response.status_code != 200:
                    LOGGER.warning(f"Failed to fetch games for {username}: {response.status_code}")
                    return
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            yield self._to_raw_game(data, username)
                        except json.JSONDecodeError as e:
                            LOGGER.warning(f"Failed to parse game JSON: {e}")
                            continue
                        
        except httpx.TimeoutException:
            LOGGER.warning(f"Timeout fetching games for {username}")
        except Exception as e:
            LOGGER.error(f"Error fetching games for {username}: {e}")
    
    def _to_raw_game(self, data: Dict[str, Any], cheater_username: str) -> RawGame:
        """Convert Lichess API game to RawGame."""
        players = data.get("players", {})
        white = players.get("white", {})
        black = players.get("black", {})
        
        white_user = white.get("user", {})
        black_user = black.get("user", {})
        
        # Determine which side is the cheater
        white_name = white_user.get("name", "")
        black_name = black_user.get("name", "")
        
        cheater_side = "none"
        if white_name.lower() == cheater_username.lower():
            cheater_side = "white"
        elif black_name.lower() == cheater_username.lower():
            cheater_side = "black"
        
        # Parse clock info from PGN
        pgn = data.get("pgn", "")
        
        return RawGame(
            source_id=data.get("id", ""),
            pgn=pgn,
            white_username=white_name,
            black_username=black_name,
            white_rating=white.get("rating"),
            black_rating=black.get("rating"),
            time_control=self._format_time_control(data.get("clock")),
            time_class=data.get("speed", "blitz"),
            game_date=self._parse_timestamp(data.get("createdAt")),
            result=self._parse_result(data.get("winner"), data.get("status")),
            metadata={
                "cheater_username": cheater_username,
                "cheater_side": cheater_side,
                "variant": data.get("variant"),
                "status": data.get("status"),
                "opening": data.get("opening", {}).get("name"),
            }
        )
    
    def get_cheater_label(self, raw: RawGame) -> CheaterLabel:
        """Determine label based on which side is the known cheater."""
        cheater_side = raw.metadata.get("cheater_side", "none") if raw.metadata else "none"
        
        return CheaterLabel(
            side=cheater_side,
            cheater_type="unknown",  # We don't know engine vs other cheating
            confirmed=True,  # Account was banned by Lichess
        )
    
    async def discover_cheaters(self, limit: int = 100) -> List[str]:
        """Discover cheaters using BFS crawl from seed players.
        
        Similar to existing discover_cheaters.py but returns usernames.
        """
        discovered = []
        seed_players = [
            "DrNykterstein", "Zhigalko_Sergei", "penguingm1",
            "Fins", "opperwezen", "DrDrunkenstein"
        ]
        
        visited: Set[str] = set()
        queue = list(seed_players)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    
                    is_cheater = await self._check_user_status(client, opponent)
                    if is_cheater:
                        discovered.append(opponent)
                        LOGGER.info(f"Discovered cheater: {opponent}")
                    else:
                        queue.append(opponent)
                    
                    await asyncio.sleep(LICHESS_API_DELAY)
        
        return discovered
    
    async def _get_recent_opponents(
        self, 
        client: httpx.AsyncClient, 
        username: str,
        limit: int = 20
    ) -> List[str]:
        """Get recent opponents of a player."""
        opponents = []
        url = f"{self.base_url}/api/games/user/{username}"
        params = {"max": limit, "pgnInJson": "false"}
        
        try:
            async with client.stream(
                "GET", url, 
                headers={**self.headers, "Accept": "application/x-ndjson"},
                params=params
            ) as response:
                if response.status_code != 200:
                    return []
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            players = data.get("players", {})
                            white = players.get("white", {}).get("user", {}).get("name", "")
                            black = players.get("black", {}).get("user", {}).get("name", "")
                            
                            if white.lower() != username.lower() and white:
                                opponents.append(white)
                            if black.lower() != username.lower() and black:
                                opponents.append(black)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            LOGGER.warning(f"Error getting opponents for {username}: {e}")
        
        return list(set(opponents))
    
    async def _check_user_status(self, client: httpx.AsyncClient, username: str) -> bool:
        """Check if a user account is closed for TOS violation."""
        url = f"{self.base_url}/api/user/{username}"
        
        try:
            response = await client.get(url, headers=self.headers)
            if response.status_code == 404:
                return False  # Account doesn't exist
            
            if response.status_code == 200:
                data = response.json()
                # Check for TOS violation
                return data.get("tosViolation", False) or data.get("disabled", False)
                
        except Exception as e:
            LOGGER.warning(f"Error checking status for {username}: {e}")
        
        return False
    
    async def get_banned_users_from_games(self, games_path: Path) -> List[str]:
        """Extract usernames from downloaded Lichess database and check status.
        
        For use with database.lichess.org monthly exports.
        """
        # This would parse PGN files and extract unique usernames
        # Then check each for ban status
        raise NotImplementedError("Use discover_cheaters() for now")
    
    @staticmethod
    def _format_time_control(clock: Optional[Dict]) -> Optional[str]:
        """Format clock data to time control string."""
        if not clock:
            return None
        
        initial = clock.get("initial", 0)
        increment = clock.get("increment", 0)
        
        if increment:
            return f"{initial}+{increment}"
        return str(initial)
    
    @staticmethod
    def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
        """Parse millisecond timestamp to datetime."""
        if not ts:
            return None
        return datetime.fromtimestamp(ts / 1000)
    
    @staticmethod
    def _parse_result(winner: Optional[str], status: Optional[str]) -> str:
        """Convert Lichess result to standard format."""
        if winner == "white":
            return "1-0"
        elif winner == "black":
            return "0-1"
        elif status in ("draw", "stalemate"):
            return "1/2-1/2"
        return "*"
