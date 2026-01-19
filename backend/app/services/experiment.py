"""Services managing experiment sessions for the hybrid dataset portal."""

from __future__ import annotations

from typing import List
from uuid import UUID, uuid4

from ..repositories import AppRepositories
from ..schemas.common import RiskFlag
from ..schemas.experiment import (
    ExperimentExport,
    ExperimentMoveLabel,
    ExperimentSession,
    ExperimentSessionRequest,
)


class ExperimentService:
    """Coordinates experiment sessions with light-weight state management."""

    def __init__(self, repositories: AppRepositories) -> None:
        self._repositories = repositories

    def start_session(self, request: ExperimentSessionRequest) -> ExperimentSession:
        """Register a new experiment session."""

        session = ExperimentSession(
            session_id=uuid4(),
            player_id=request.player_id,
            mode=request.mode,
            status="running",
            metadata=request.metadata,
        )

        if request.mode != "clean":
            session.flags.append(
                RiskFlag(
                    code="assisted_mode",
                    message="Session configured for assisted play; ensure labeling accuracy.",
                    severity="medium",
                )
            )

        self._repositories.experiments.save_session(session)
        return session

    def complete_session(
        self, session_id: UUID, pgn: str, move_notes: List[ExperimentMoveLabel]
    ) -> ExperimentExport:
        """Persist an export for a completed session."""

        export = ExperimentExport(session_id=session_id, pgn=pgn, move_labels=move_notes)
        self._repositories.experiments.save_export(export)
        session = self._repositories.experiments.get_session(session_id)
        updated_session = session.model_copy(update={"status": "completed"})
        self._repositories.experiments.save_session(updated_session)
        return export

    def get_export(self, session_id: UUID) -> ExperimentExport:
        """Fetch an export for a session, generating a placeholder if necessary."""

        try:
            return self._repositories.experiments.get_export(session_id)
        except KeyError:
            session = self._repositories.experiments.get_session(session_id)
            placeholder_notes = [
                ExperimentMoveLabel(
                    ply=1,
                    label="human_clean" if session.mode == "clean" else "assisted_move",
                    confidence=0.6,
                )
            ]
            placeholder_pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1/2-1/2"
            return self.complete_session(session_id, placeholder_pgn, placeholder_notes)

