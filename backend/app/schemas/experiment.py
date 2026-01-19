"""Schemas for the experiment portal domain."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import AuditMetadata, RiskFlag


class ExperimentSessionRequest(BaseModel):
    """Request payload to start a controlled experiment session."""

    player_id: str = Field(..., description="Identifier of the volunteer player.")
    mode: str = Field(..., description="Experiment mode such as clean or assisted_20.")
    consent: bool = Field(..., description="Whether the player has provided informed consent.")
    time_control: Optional[str] = Field(None, description="Time control for the experiment game.")
    metadata: Dict[str, str] = Field(default_factory=dict)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        allowed = {"clean", "assisted_10", "assisted_20", "assisted_40"}
        if value not in allowed:
            raise ValueError(f"mode must be one of {sorted(allowed)}")
        return value

    @field_validator("consent")
    @classmethod
    def validate_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent must be explicitly granted before starting an experiment.")
        return value


class ExperimentSession(BaseModel):
    """Represents a running or completed experiment session."""

    session_id: UUID
    player_id: str
    mode: str
    status: str = Field(..., description="Session status: pending, running, completed.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = Field(default_factory=dict)
    audit: AuditMetadata = Field(default_factory=AuditMetadata)
    flags: List[RiskFlag] = Field(default_factory=list)


class ExperimentMoveLabel(BaseModel):
    """Label attached to a move within an experiment session."""

    ply: int = Field(..., ge=1)
    label: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    notes: Optional[str] = None


class ExperimentCompletionRequest(BaseModel):
    """Payload to mark an experiment session as completed."""

    pgn: str
    move_labels: List[ExperimentMoveLabel]


class ExperimentExport(BaseModel):
    """Data exported from an experiment session for dataset curation."""

    session_id: UUID
    pgn: str
    move_labels: List[ExperimentMoveLabel]
    notes: List[str] = Field(default_factory=list)


class ExperimentMoveEvaluation(BaseModel):
    """Lightweight serialisable view of an engine evaluation."""

    fen: str
    depth: Optional[int] = None
    score_cp: Optional[int] = None
    mate_in: Optional[int] = None
    pv: List[str] = Field(default_factory=list)
    bestmove: Optional[str] = None
    raw_info: List[str] = Field(default_factory=list)

    @classmethod
    def from_engine_dict(cls, payload: Dict[str, object]) -> "ExperimentMoveEvaluation":
        """Construct from a dictionary produced by :class:`EngineEvaluation`."""

        return cls.model_validate(payload)


class ExperimentSessionMove(BaseModel):
    """Single move recorded during an interactive experiment session."""

    ply: int
    actor: Literal["human", "engine"]
    move_uci: str
    move_san: str
    fen_before: str
    evaluation: ExperimentMoveEvaluation
    reference: Optional[ExperimentMoveEvaluation] = Field(
        default=None,
        description="Engine best-line evaluation for comparison on human moves.",
    )
    centipawn_loss: Optional[int] = Field(
        default=None,
        description="Centipawn loss relative to the best line for human moves.",
    )
    label: str = Field(
        ..., description="Training label describing the actor or move quality."
    )


class ExperimentSessionState(BaseModel):
    """Current state of an interactive experiment session."""

    session: ExperimentSession
    board_fen: str
    moves: List[ExperimentSessionMove] = Field(default_factory=list)
    history: List[str] = Field(
        default_factory=list,
        description="Move history encoded as a sequence of UCI strings.",
    )
    next_to_move: str = Field(
        ..., description="Colour to move next in algebraic notation (white/black)."
    )
    outcome: Optional[str] = Field(
        default=None,
        description="Result string when the game has concluded (e.g., 1-0, 0-1, 1/2-1/2).",
    )


class ExperimentMoveResponse(BaseModel):
    """Response envelope for a move submission including updated state."""

    player: Optional[ExperimentSessionMove] = None
    engine: Optional[ExperimentSessionMove] = None
    state: ExperimentSessionState
    export: Optional[ExperimentExport] = None

