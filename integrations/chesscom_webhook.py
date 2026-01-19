"""Adapter for Chess.com live game webhooks."""

from __future__ import annotations

from typing import Any, Dict

import requests

from chessguard.models import LivePGNSubmission


class ChessComWebhookAdapter:
    """Transforms Chess.com webhook payloads into ChessGuard submissions."""

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        submission = self.to_submission(payload)
        return self._submit(submission)

    def to_submission(self, payload: Dict[str, Any]) -> LivePGNSubmission:
        game = payload.get("game", payload)
        players = game.get("players", {})
        suspect = payload.get("suspect") or players.get("white") or players.get("player")
        opponent = players.get("black") if suspect is players.get("white") else players.get("white")

        metadata = {
            "source": "chess.com",
            "engine_agreement": payload.get("engine_agreement"),
            "average_centipawn_loss": payload.get("average_centipawn_loss"),
            "time_anomalies": payload.get("time_anomalies"),
            "prior_flags": payload.get("prior_flags"),
            "opponent": opponent.get("username") if isinstance(opponent, dict) else opponent,
        }
        metadata = {key: value for key, value in metadata.items() if value is not None}

        return LivePGNSubmission(
            event_id=str(payload.get("event_id") or game.get("tournament_id") or "chesscom-live"),
            player_id=str(payload.get("player_id") or self._player_username(suspect)),
            round=payload.get("round"),
            pgn=game.get("pgn", ""),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    def _player_username(self, data: Any) -> str:
        if isinstance(data, dict):
            return str(data.get("username") or data.get("id") or "unknown")
        if data:
            return str(data)
        return "unknown"

    def _submit(self, submission: LivePGNSubmission) -> Dict[str, Any]:
        response = requests.post(
            f"{self.api_url}/games",
            headers={"X-API-Key": self.api_key},
            json=submission.dict(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


__all__ = ["ChessComWebhookAdapter"]
