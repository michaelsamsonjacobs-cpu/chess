"""Shared models for the ChessGuard backend (Lichess integration).

This module combines:
- Pydantic schemas (request/response models for the FastAPI layer)
- SQLAlchemy ORM models (persistence layer)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from ..database import Base


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


# Game class definition removed to avoid conflict with server.models.game.Game



class UserProfile(Base):
    __tablename__ = "profiles_v2"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    bio = Column(String, nullable=True)
    rating = Column(Integer, default=1200, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LichessAccount(Base):
    """Persisted integration metadata for a ChessGuard user."""

    __tablename__ = "lichess_accounts_v2"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(Integer, unique=True, nullable=False, index=True)
    lichess_username: Mapped[Optional[str]] = Column(String(255), nullable=True)
    access_token: Mapped[Optional[str]] = Column(String(255), nullable=True)
    last_synced: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    games: Mapped[List["LichessGame"]] = relationship(
        "LichessGame", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )
    reports: Mapped[List["LichessReport"]] = relationship(
        "LichessReport", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )


class LichessGame(Base):
    """Snapshot of a synchronised Lichess game."""

    __tablename__ = "lichess_games_v2"
    __table_args__ = (UniqueConstraint("account_id", "lichess_id", name="uq_lichess_games_account_v2"),)

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = Column(Integer, ForeignKey("lichess_accounts_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    lichess_id: Mapped[str] = Column(String(64), nullable=False)
    data: Mapped[Dict[str, object]] = Column(JSON, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    account: Mapped[LichessAccount] = relationship("LichessAccount", back_populates="games")


class LichessReport(Base):
    """Cheat reports that have been forwarded to Lichess."""

    __tablename__ = "lichess_reports_v2"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = Column(
        Integer, ForeignKey("lichess_accounts_v2.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[str] = Column(String(64), nullable=False)
    player_id: Mapped[str] = Column(String(64), nullable=False)
    reason: Mapped[str] = Column(String(64), nullable=False)
    description: Mapped[Optional[str]] = Column(Text, nullable=True)
    status_code: Mapped[int] = Column(Integer, nullable=False)
    message: Mapped[Optional[str]] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    account: Mapped[LichessAccount] = relationship("LichessAccount", back_populates="reports")


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
    "Game",
    "UserProfile",
    "LichessAccount",
    "LichessGame",
    "LichessReport",
    "Player",
]

# Import Player model
from .player import Player
