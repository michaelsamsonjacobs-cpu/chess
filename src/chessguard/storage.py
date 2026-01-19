"""In-memory persistence layer for ChessGuard services."""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .models import Alert, LiveGame, LivePGNSubmission, ModelExplanation, RiskAssessment


class GameRepository:
    """Thread-safe repository that stores games in memory.

    The repository is designed so that it can be swapped with a database-backed
    implementation later without changing calling code.  For the prototype
    environment the in-memory store keeps things simple while we integrate live
    feeds.
    """

    def __init__(self) -> None:
        self._games: Dict[str, LiveGame] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Core CRUD operations
    # ------------------------------------------------------------------
    def add_game(
        self,
        submission: LivePGNSubmission,
        risk: RiskAssessment,
        explanation: ModelExplanation,
        submitted_by: str,
    ) -> LiveGame:
        """Persist a submitted game and return the canonical record."""

        game_id = str(uuid4())
        record = LiveGame(
            id=game_id,
            event_id=submission.event_id,
            player_id=submission.player_id,
            round=submission.round,
            pgn=submission.pgn,
            risk=risk,
            explanation=explanation,
            submitted_at=datetime.utcnow(),
            submitted_by=submitted_by,
            metadata=submission.metadata,
        )
        with self._lock:
            self._games[game_id] = record
        return record

    def get_game(self, game_id: str) -> Optional[LiveGame]:
        """Retrieve a stored game by its identifier."""

        with self._lock:
            return self._games.get(game_id)

    def list_event_games(self, event_id: str) -> List[LiveGame]:
        """Return games for an event ordered by submission time (desc)."""

        with self._lock:
            games = [game for game in self._games.values() if game.event_id == event_id]
        return sorted(games, key=lambda game: game.submitted_at, reverse=True)

    def list_recent(self, limit: int = 20) -> List[LiveGame]:
        """Return the most recent games regardless of event."""

        with self._lock:
            games = list(self._games.values())
        games.sort(key=lambda game: game.submitted_at, reverse=True)
        return games[:limit]

    # ------------------------------------------------------------------
    # Derived views
    # ------------------------------------------------------------------
    def generate_alerts(
        self,
        games: Iterable[LiveGame],
        threshold: float,
    ) -> List[Alert]:
        alerts: List[Alert] = []
        for game in games:
            if game.risk.score >= threshold:
                alerts.append(
                    Alert(
                        game_id=game.id,
                        event_id=game.event_id,
                        player_id=game.player_id,
                        risk_score=game.risk.score,
                        tier=game.risk.tier,
                        message=f"Game {game.id} flagged with score {game.risk.score:.1f}",
                        recommended_actions=game.risk.recommended_actions,
                        submitted_at=game.submitted_at,
                        submitted_by=game.submitted_by,
                    )
                )
        return alerts

    def get_alerts_for_event(self, event_id: str, threshold: float = 70.0) -> List[Alert]:
        """Return alerts for a particular event."""

        games = self.list_event_games(event_id)
        return self.generate_alerts(games, threshold)

    def get_global_alerts(self, threshold: float = 70.0, limit: int = 20) -> List[Alert]:
        """Return alerts across events for quick dashboards."""

        games = self.list_recent(limit=limit)
        return self.generate_alerts(games, threshold)
