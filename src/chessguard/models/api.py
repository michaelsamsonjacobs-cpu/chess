"""Core data models for ChessGuard services.

These models define the shape of live game submissions, risk assessments,
alerts, and audit events shared between the API service, CLI, and integration
adapters.  They intentionally avoid persistence concerns so that the same
objects can be reused for in-memory stores or future database backends.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    """Summary of a risk assessment generated for a submitted PGN."""

    score: float = Field(..., ge=0, le=100)
    tier: str = Field(..., description="Descriptive label for the risk tier")
    recommended_actions: List[str] = Field(
        default_factory=list,
        description="Follow-up actions recommended for tournament staff.",
    )


class ModelExplanation(BaseModel):
    """Explainability payload describing the model's reasoning."""

    summary: str
    top_factors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Key factors contributing to the assessment.",
    )


class LivePGNSubmission(BaseModel):
    """Schema for ingesting a live PGN from the API or an integration."""

    event_id: str
    player_id: str
    round: Optional[int] = Field(None, description="Round number when available")
    pgn: str = Field(..., description="Portable Game Notation for the live game")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LiveGame(BaseModel):
    """Canonical record for a game tracked by the system."""

    id: str
    event_id: str
    player_id: str
    round: Optional[int]
    pgn: str
    risk: RiskAssessment
    explanation: ModelExplanation
    submitted_at: datetime
    submitted_by: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Alert(BaseModel):
    """Alert surfaced to staff when a game's risk exceeds a threshold."""

    game_id: str
    event_id: str
    player_id: str
    risk_score: float
    tier: str
    message: str
    recommended_actions: List[str] = Field(default_factory=list)
    submitted_at: datetime
    submitted_by: str


class AuditEvent(BaseModel):
    """Structured audit event for compliance tracking."""

    timestamp: datetime
    actor: str
    action: str
    resource: str
    status_code: int
    latency_ms: float
    detail: Dict[str, Any] = Field(default_factory=dict)
