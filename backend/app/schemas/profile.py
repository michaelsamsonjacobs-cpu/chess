"""Pydantic schemas for profile ingestion and analytics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .common import AuditMetadata, RiskFlag


class ProfileGameReference(BaseModel):
    """Reference to a previously ingested game when aggregating a profile."""

    game_id: UUID
    result: Optional[str] = Field(None, description="Result string such as 1-0, 0-1, or 1/2-1/2.")
    rated: Optional[bool] = Field(None, description="Whether the referenced game was rated.")


class ProfileIngestRequest(BaseModel):
    """Payload used to ingest a player profile for analytics."""

    profile_id: str = Field(..., description="Identifier of the profile on the source platform.")
    platform: str = Field(..., description="Source platform such as lichess or chesscom.")
    join_date: Optional[date] = Field(None, description="Date the account was created.")
    last_active: Optional[date] = Field(None, description="Date of the most recent activity.")
    total_games: Optional[int] = Field(None, ge=0)
    ratings: Dict[str, int] = Field(default_factory=dict, description="Ratings by variant/time control.")
    recent_games: List[ProfileGameReference] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfileAnalytics(BaseModel):
    """Analytics calculated for a profile across multiple games."""

    profile_id: str
    platform: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    rating_anomaly: float = Field(..., description="Deviation between reported and inferred strength.")
    activity_burst_index: float = Field(..., description="Magnitude of clustered activity patterns.")
    fatigue_drift: float = Field(..., description="Trend of reaction times across sessions.")
    tilt_drift: float = Field(..., description="Volatility of performance following losses.")
    psych_consistency: float = Field(..., description="Consistency of psychological signals across games.")
    aggregate_engine_match: float = Field(..., description="Average engine match rate across recent games.")
    game_count: int = Field(..., ge=0)
    suspicious_game_ratio: float = Field(..., ge=0.0, le=1.0)
    flags: List[RiskFlag] = Field(default_factory=list)
    audit: AuditMetadata = Field(default_factory=AuditMetadata)


class ProfileReport(BaseModel):
    """Detailed report for a profile including narrative text."""

    analytics: ProfileAnalytics
    summary: str


class ProfileRecord(BaseModel):
    """Internal storage record for a profile and its analytics."""

    id: str
    request: ProfileIngestRequest
    analytics: ProfileAnalytics
    created_at: datetime = Field(default_factory=datetime.utcnow)

