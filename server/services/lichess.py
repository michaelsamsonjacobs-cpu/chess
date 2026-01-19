"""Wrappers around the Lichess public API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LichessAPIError(RuntimeError):
    """Raised when Lichess returns an unexpected response."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LichessRateLimitError(LichessAPIError):
    """Raised when the remote API signals that the caller is rate limited."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after


class LichessService:
    """Utility class responsible for interacting with the Lichess REST API."""

    def __init__(
        self,
        *,
        base_url: str = "https://lichess.org",
        rate_limit_per_sec: float = 1.0,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self._lock = asyncio.Lock()
        self._min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._last_call = 0.0

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()

    async def _throttle(self) -> None:
        """Ensure that outbound requests obey the configured rate limit."""

        if self._min_interval <= 0:
            return
        async with self._lock:
            elapsed = time.perf_counter() - self._last_call
            sleep_for = self._min_interval - elapsed
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            self._last_call = time.perf_counter()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        token: Optional[str],
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform an HTTP request against the Lichess API."""

        await self._throttle()
        request_headers = {
            "User-Agent": "ChessGuard/0.1 (+https://github.com/ChessGuard)",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        try:
            response = await self._client.request(
                method,
                url,
                headers=request_headers,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise LichessAPIError(f"Network error communicating with Lichess: {exc}") from exc

        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After")
            retry_after = float(retry_after_header) if retry_after_header else None
            raise LichessRateLimitError(
                "Lichess API rate limit exceeded.",
                status_code=response.status_code,
                retry_after=retry_after,
            )

        if response.status_code >= 400:
            detail: str
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                payload = response.json()
                detail = json.dumps(payload)
            else:
                detail = response.text
            raise LichessAPIError(
                f"Lichess API responded with {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        return response

    async def fetch_recent_games(
        self,
        username: str,
        token: str,
        *,
        max_games: int = 20,
        since: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Download a user's recent games and return normalised summaries."""

        params: Dict[str, Any] = {
            "max": max_games,
            "moves": "true",
            "pgnInJson": "true",
            "opening": "true",
        }
        if since is not None:
            params["since"] = since
        headers = {"Accept": "application/x-ndjson"}
        response = await self._request(
            "GET",
            f"/api/games/user/{username}",
            token=token,
            params=params,
            headers=headers,
        )

        raw_text = response.text.strip()
        if not raw_text:
            return []

        games: List[Dict[str, Any]] = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Failed to decode game payload: %s", line)
                continue
            games.append(self._normalise_game(payload))
        return games

    async def submit_cheat_report(
        self,
        token: str,
        *,
        game_id: str,
        player_id: str,
        reason: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a cheating report to the Lichess moderation endpoint."""

        payload = {
            "gameId": game_id,
            "player": player_id,
            "reason": reason,
            "text": description or "",
        }
        headers = {"Content-Type": "application/json"}
        response = await self._request(
            "POST",
            "/api/report/cheat",
            token=token,
            json=payload,
            headers=headers,
        )
        content_type = response.headers.get("Content-Type", "")
        body: Any
        if "application/json" in content_type:
            body = response.json()
        else:
            body = response.text or None
        return {
            "status_code": response.status_code,
            "detail": body,
        }

    def _normalise_game(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a raw Lichess game payload into a compact summary."""

        players = payload.get("players", {})
        white_name = self._extract_player_name(players.get("white"))
        black_name = self._extract_player_name(players.get("black"))
        moves_san = payload.get("moves")
        move_count: Optional[int]
        if isinstance(moves_san, str) and moves_san:
            move_count = len(moves_san.split())
        else:
            move_count = None
        summary = {
            "id": payload.get("id"),
            "url": f"{self.base_url}/{payload.get('id')}",
            "rated": payload.get("rated"),
            "speed": payload.get("speed"),
            "createdAt": payload.get("createdAt"),
            "lastMoveAt": payload.get("lastMoveAt"),
            "white": white_name,
            "black": black_name,
            "winner": payload.get("winner"),
            "status": payload.get("status"),
            "moves": move_count,
            "pgn": payload.get("pgn"),
        }
        opening = payload.get("opening")
        if isinstance(opening, dict):
            summary["opening"] = opening.get("name")
        return summary

    @staticmethod
    def _extract_player_name(player_payload: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(player_payload, dict):
            return None
        user = player_payload.get("user")
        if isinstance(user, dict):
            return user.get("name") or user.get("id")
        return player_payload.get("name")
