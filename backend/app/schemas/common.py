"""Shared pydantic schemas for the ChessGuard API."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class TimingStats(BaseModel):
    """Summary statistics for per-move reaction times."""

    mean: float = Field(0.0, description="Average reaction time in seconds.")
    median: float = Field(0.0, description="Median reaction time in seconds.")
    std_dev: float = Field(0.0, description="Population standard deviation in seconds.")
    count: int = Field(0, description="Number of moves with reaction times.")


class AuditMetadata(BaseModel):
    """Standard metadata returned alongside analytic responses."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field("0.1.0", description="Semantic version for the analytics pipeline.")
    parameters: Dict[str, float] = Field(default_factory=dict, description="Key hyper-parameters used.")


class PaginatedResponse(BaseModel):
    """Simple pagination envelope used for list endpoints."""

    total: int
    limit: int
    offset: int
    items: list


class RiskFlag(BaseModel):
    """Represents a human readable flag or note."""

    code: str
    message: str
    severity: str = Field("medium", description="Severity label: low/medium/high/critical.")
    context: Optional[Dict[str, str]] = None

