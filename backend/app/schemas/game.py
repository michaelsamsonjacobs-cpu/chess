"""Pydantic schemas for game ingestion and analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import AuditMetadata, RiskFlag, TimingStats


class MoveTiming(BaseModel):
    """Represents the timing information for a single move."""

    ply: int = Field(..., ge=1, description="Ply index starting at 1.")
    time_seconds: float = Field(..., ge=0.0, description="Reaction time for the move in seconds.")
    increment_seconds: Optional[float] = Field(None, ge=0.0, description="Increment added after the move.")
    timestamp: Optional[datetime] = Field(None, description="Wall-clock timestamp when the move was played.")


class GameIngestRequest(BaseModel):
    """Payload used to ingest a game for analysis."""

    source: str = Field(..., description="Origin of the game: lichess, chesscom, upload, etc.")
    pgn: str = Field(..., description="Portable Game Notation string for the game.")
    player_id: Optional[str] = Field(None, description="Identifier of the player being audited.")
    opponent_id: Optional[str] = Field(None, description="Identifier of the opponent.")
    rated: Optional[bool] = Field(True, description="Whether the game was rated.")
    time_control: Optional[str] = Field(None, description="Time control string, e.g. 3+2.")
    event: Optional[str] = Field(None, description="Event or tournament name.")
    move_timings: Optional[List[MoveTiming]] = Field(
        None, description="Optional list of per-move reaction times and metadata."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata captured during ingest.")

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        allowed = {"lichess", "chesscom", "upload", "experiment"}
        if value not in allowed:
            raise ValueError(f"source must be one of {sorted(allowed)}")
        return value

    @field_validator("pgn")
    @classmethod
    def validate_pgn(cls, value: str) -> str:
        if " " not in value:
            raise ValueError("PGN appears to be invalid or truncated.")
        return value.strip()


class GameFeatures(BaseModel):
    """Core analytic features computed for a game."""

    total_moves: int = Field(..., ge=1)
    engine_match_rate_top1: float = Field(..., ge=0.0, le=1.0)
    engine_match_rate_top3: float = Field(..., ge=0.0, le=1.0)
    hick_hyman_slope: float = Field(..., description="Slope of RT vs. decision complexity.")
    post_error_slowing: float = Field(..., description="Average increase in RT after a flagged mistake.")
    speed_accuracy_frontier: float = Field(..., description="Composite of accuracy vs. speed trade-off.")
    log_normal_rt_variance: float = Field(..., description="Variance of log reaction times.")
    average_reaction_time: float = Field(..., description="Mean reaction time across moves.")
    reaction_time_stats: TimingStats = Field(default_factory=TimingStats)
    complexity_index: float = Field(..., description="Composite of move complexity across the game.")
    accuracy_trend: float = Field(..., description="Trend of accuracy throughout the game (-1..1 range).")


class GameAnalysis(BaseModel):
    """Full analysis payload returned for a game."""

    game_id: UUID
    features: GameFeatures
    suspicion_score: float = Field(..., ge=0.0, le=1.0)
    audit: AuditMetadata = Field(default_factory=AuditMetadata)
    flags: List[RiskFlag] = Field(default_factory=list)


class GameIngestResponse(BaseModel):
    """Response returned when a game is ingested."""

    game_id: UUID
    analysis: GameAnalysis


class GameReport(BaseModel):
    """Detailed report view for a game with explanations."""

    game_id: UUID
    features: GameFeatures
    suspicion_score: float
    summary: str
    flags: List[RiskFlag]
    audit: AuditMetadata


class GameRecord(BaseModel):
    """Internal storage model for an ingested game and its analysis."""

    id: UUID
    request: GameIngestRequest
    analysis: GameAnalysis
    created_at: datetime = Field(default_factory=datetime.utcnow)

