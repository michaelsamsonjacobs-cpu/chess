
import httpx
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

CHESSCOM_API_BASE = "https://api.chess.com/pub"

class ChessComService:
    def __init__(self):
        self.headers = {
            "User-Agent": "ChessGuard/1.0 (contact@chessguard.dev)" # Required by Chess.com
        }
        self.timeout = 30.0  # Increased timeout

    async def _get(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching {url}: {type(e).__name__}: {e}")
            raise

    async def get_player_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch player profile including account status."""
        try:
            url = f"{CHESSCOM_API_BASE}/player/{username}"
            data = await self._get(url)
            
            # Parse account status
            status = data.get("status", "")
            data["is_closed"] = status.startswith("closed")
            data["is_fair_play_violation"] = "fair_play" in status.lower()
            data["violation_type"] = status if data["is_closed"] else None
            
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def check_account_status(self, username: str) -> Dict[str, Any]:
        """Check if an account is closed or has violations.
        
        Returns:
            Dict with keys: is_active, is_closed, violation_type, status_message
        """
        profile = await self.get_player_profile(username)
        if not profile:
            return {
                "is_active": False,
                "is_closed": True,
                "violation_type": "not_found",
                "status_message": "Account not found"
            }
        
        status = profile.get("status", "")
        is_closed = profile.get("is_closed", False)
        is_fair_play = profile.get("is_fair_play_violation", False)
        
        if is_fair_play:
            return {
                "is_active": False,
                "is_closed": True,
                "violation_type": "fair_play",
                "status_message": "Account closed for fair play violations"
            }
        elif is_closed:
            return {
                "is_active": False,
                "is_closed": True,
                "violation_type": status,
                "status_message": f"Account closed: {status}"
            }
        else:
            return {
                "is_active": True,
                "is_closed": False,
                "violation_type": None,
                "status_message": "Account active - No fair play violations detected"
            }

    async def get_player_archives(self, username: str) -> List[str]:
        """Fetch list of monthly archive URLs."""
        url = f"{CHESSCOM_API_BASE}/player/{username}/games/archives"
        data = await self._get(url)
        return data.get("archives", [])

    async def get_games_from_archive(self, archive_url: str) -> List[Dict[str, Any]]:
        """Fetch games from a specific monthly archive."""
        try:
            data = await self._get(archive_url)
            return data.get("games", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Archive doesn't exist (no games that month) - return empty
                logger.warning(f"Archive not found (404): {archive_url}")
                return []
            raise

    async def get_recent_games(self, username: str, limit_months: int = 1) -> List[Dict[str, Any]]:
        """Fetch games from the last N months."""
        archives = await self.get_player_archives(username)
        if not archives:
            return []
        
        # Take the last N archives (months)
        recent_archives = archives[-limit_months:]
        all_games = []
        
        for url in recent_archives:
            try:
                games = await self.get_games_from_archive(url)
                all_games.extend(games)
            except Exception as e:
                logger.warning(f"Failed to fetch archive {url}: {e}")
                continue
            
        return all_games

chesscom_service = ChessComService()
