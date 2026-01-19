"""Adapter for Lichess live event webhooks."""

from __future__ import annotations

from typing import Any, Dict

import requests

from chessguard.models import LivePGNSubmission


class LichessWebhookAdapter:
    """Transforms Lichess payloads into ChessGuard submissions."""

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        submission = self.to_submission(payload)
        return self._submit(submission)

    def to_submission(self, payload: Dict[str, Any]) -> LivePGNSubmission:
        game = payload.get("game", payload)
        players = game.get("players", {})
        focus_player = payload.get("focus") or players.get("white") or players.get("player")
        opponent = players.get("black") if focus_player is players.get("white") else players.get("white")

        metadata = {
            "source": "lichess",
            "engine_agreement": payload.get("engineAgreement"),
            "average_centipawn_loss": payload.get("acpl"),
            "time_anomalies": payload.get("timeAnomalies"),
            "prior_flags": payload.get("priorFlags"),
            "opponent": self._player_identifier(opponent),
            "performance": payload.get("performance"),
        }
        metadata = {key: value for key, value in metadata.items() if value is not None}

        return LivePGNSubmission(
            event_id=str(payload.get("eventId") or game.get("event", {}).get("id") or "lichess-live"),
            player_id=self._player_identifier(focus_player),
            round=payload.get("round"),
            pgn=game.get("pgn", ""),
            metadata=metadata,
        )

    def _player_identifier(self, data: Any) -> str:
        if isinstance(data, dict):
            return str(data.get("id") or data.get("name") or data.get("username") or "unknown")
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


__all__ = ["LichessWebhookAdapter"]
