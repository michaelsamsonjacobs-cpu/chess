"""Shared models for the ChessGuard backend (Lichess integration).

This module combines:
- Pydantic schemas (request/response models for the FastAPI layer)
- SQLAlchemy ORM models (persistence layer)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Integer, String

from .database import Base


# =============================================================================
# Pydantic request/response models (API layer)
# =============================================================================


class LichessConnectRequest(BaseModel):
    """Payload for connecting a user account to Lichess."""

    username: str = Field(..., min_length=1, description="Lichess username")
    access_token: str = Field(
        ...,
        alias="accessToken",
        min_length=1,
        description="OAuth or personal access token issued by Lichess.",
    )

    model_config = ConfigDict(populate_by_name=True)


class SyncGamesRequest(BaseModel):
    """Parameters that control how many games are synchronised."""

    max_games: int = Field(
        20,
        alias="maxGames",
        ge=1,
        le=200,
        description="Maximum number of recent games to fetch from Lichess.",
    )
    since: Optional[int] = Field(
        None,
        description=(
            "Fetch only games created after the provided UNIX timestamp in"
            " milliseconds."
        ),
    )

    model_config = ConfigDict(populate_by_name=True)


class LichessReportRequest(BaseModel):
    """Payload used when reporting a suspected cheater to Lichess."""

    game_id: str = Field(..., alias="gameId", description="Identifier of the game.")
    player_id: str = Field(
        ...,
        alias="playerId",
        description="Lichess username of the suspected cheater.",
    )
    reason: str = Field(
        "cheat",
        description="Reason string accepted by the Lichess report endpoint.",
    )
    description: Optional[str] = Field(
        None,
        description="Additional information for the Lichess moderation team.",
    )

    model_config = ConfigDict(populate_by_name=True)


class GameSummary(BaseModel):
    """A trimmed representation of a Lichess game used by the UI."""

    id: str
    url: str
    rated: Optional[bool] = None
    speed: Optional[str] = None
    created_at: Optional[int] = Field(None, alias="createdAt")
    last_move_at: Optional[int] = Field(None, alias="lastMoveAt")
    white: Optional[str] = None
    black: Optional[str] = None
    winner: Optional[str] = None
    status: Optional[str] = None
    moves: Optional[int] = None
    pgn: Optional[str] = None
    opening: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class SyncGamesResponse(BaseModel):
    """Response returned after synchronising games with Lichess."""

    count: int
    last_sync: datetime = Field(..., alias="lastSync")
    games: List[GameSummary]

    model_config = ConfigDict(populate_by_name=True)


class ReportRecordModel(BaseModel):
    """Public representation of a stored cheat report."""

    game_id: str = Field(..., alias="gameId")
    player_id: str = Field(..., alias="playerId")
    reason: str
    description: Optional[str] = None
    created_at: datetime = Field(..., alias="createdAt")
    status_code: int = Field(..., alias="statusCode")
    message: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class LichessReportResponse(BaseModel):
    """Response payload returned when a report submission succeeds."""

    status: str
    report: ReportRecordModel


class UserStateResponse(BaseModel):
    """Snapshot of the current user state returned to the frontend."""

    user_id: str = Field(..., alias="userId")
    lichess_username: Optional[str] = Field(None, alias="lichessUsername")
    connected: bool
    last_sync: Optional[datetime] = Field(None, alias="lastSync")
    games: List[GameSummary]
    reports: List[ReportRecordModel]

    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# SQLAlchemy ORM models (DB layer)
# =============================================================================


class LegacyGame(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    opponent = Column(String(255), nullable=False)
    result = Column(String(50), nullable=False)
    moves = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserProfile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    bio = Column(String, nullable=True)
    rating = Column(Integer, default=1200, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


__all__ = [
    # Pydantic schemas
    "LichessConnectRequest",
    "SyncGamesRequest",
    "LichessReportRequest",
    "GameSummary",
    "SyncGamesResponse",
    "ReportRecordModel",
    "LichessReportResponse",
    "UserStateResponse",
    # ORM models
    "LegacyGame",
    "UserProfile",
]
