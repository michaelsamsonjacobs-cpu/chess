"""Schemas for moderation and labeling workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .common import RiskFlag


class ModerationLabelRequest(BaseModel):
    """Request to attach a moderation label to a game or profile."""

    target_id: str = Field(..., description="Identifier of the game or profile being labeled.")
    target_type: str = Field(..., description="Type of target, e.g., game or profile.")
    label: str = Field(..., description="Label name such as clean_human or engine_assist.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    notes: Optional[str] = Field(None)


class ModerationLabel(BaseModel):
    """Representation of a moderation decision for audit purposes."""

    label_id: UUID
    target_id: str
    target_type: str
    label: str
    confidence: float
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    flags: list[RiskFlag] = Field(default_factory=list)


class ModerationQueueEntry(BaseModel):
    """Entry representing a pending review in the moderation queue."""

    target_id: str
    target_type: str
    reason: str
    suggested_action: Optional[str] = None
    priority: str = Field("medium", description="low, medium, or high priority.")

