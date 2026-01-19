from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship

from server.database import Base


class InvestigationStatus(str, enum.Enum):
    """Enumeration of supported investigation states."""

    PENDING = "pending"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FLAGGED = "flagged"
    ERROR = "error"


class BatchAnalysisStatus(str, enum.Enum):
    """Status of a batch analysis job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class RiskLevel(str, enum.Enum):
    """Risk level for batch analysis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users_v2"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    username: Mapped[str] = Column(String(255), nullable=False, unique=True, index=True)
    lichess_username: Mapped[Optional[str]] = Column(String(255), unique=True, index=True)
    lichess_token: Mapped[Optional[str]] = Column(String(255), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    games_as_white: Mapped[List["Game"]] = relationship(
        "Game", back_populates="white_player", foreign_keys="Game.white_id", cascade="all, delete"
    )
    games_as_black: Mapped[List["Game"]] = relationship(
        "Game", back_populates="black_player", foreign_keys="Game.black_id", cascade="all, delete"
    )


class BatchAnalysis(Base):
    """Batch analysis job tracking."""
    __tablename__ = "batch_analyses"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    source: Mapped[str] = Column(String(32), nullable=False)  # "lichess" or "chesscom"
    username: Mapped[str] = Column(String(255), nullable=False, index=True)
    total_games: Mapped[int] = Column(Integer, default=0, nullable=False)
    analyzed_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    flagged_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    reported_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    avg_suspicion: Mapped[float] = Column(Float, default=0.0, nullable=False)
    risk_level: Mapped[Optional[RiskLevel]] = Column(Enum(RiskLevel))
    
    # Streak Improbability Score fields
    longest_win_streak: Mapped[int] = Column(Integer, default=0, nullable=False)
    streak_improbability_score: Mapped[float] = Column(Float, default=0.0, nullable=False)
    suspicious_streak_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    max_streak_improbability: Mapped[float] = Column(Float, default=0.0, nullable=False)
    
    timeframe: Mapped[Optional[str]] = Column(String(16), default="1m") # "1m", "3m", "all", etc.
    status: Mapped[BatchAnalysisStatus] = Column(
        Enum(BatchAnalysisStatus), default=BatchAnalysisStatus.QUEUED, nullable=False
    )
    error_message: Mapped[Optional[str]] = Column(Text)
    started_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))

    # Relationships
    games: Mapped[List["Game"]] = relationship(
        "Game", back_populates="batch_analysis", foreign_keys="Game.batch_id"
    )


class Game(Base):
    __tablename__ = "games_v3"
    __table_args__ = (UniqueConstraint("lichess_id", name="uq_games_lichess_id"),)

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    lichess_id: Mapped[str] = Column(String(255), nullable=False) # Increased size mainly for external URLs/IDs
    source: Mapped[str] = Column(String(32), default="lichess", nullable=False)
    played_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    white_id: Mapped[int] = Column(Integer, ForeignKey("users_v2.id"), nullable=False)
    black_id: Mapped[int] = Column(Integer, ForeignKey("users_v2.id"), nullable=False)
    result: Mapped[Optional[str]] = Column(String(8))
    pgn: Mapped[Optional[str]] = Column(Text)
    analysis_status: Mapped[InvestigationStatus] = Column(
        Enum(InvestigationStatus), default=InvestigationStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    batch_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("batch_analyses.id", use_alter=True, name="fk_games_batch_id"), index=True)

    white_player: Mapped[User] = relationship(
        "User", back_populates="games_as_white", foreign_keys=[white_id], lazy="joined"
    )
    black_player: Mapped[User] = relationship(
        "User", back_populates="games_as_black", foreign_keys=[black_id], lazy="joined"
    )
    evaluations: Mapped[List["EngineEvaluation"]] = relationship(
        "EngineEvaluation", back_populates="game", cascade="all, delete-orphan", lazy="selectin"
    )
    investigation: Mapped[Optional["Investigation"]] = relationship(
        "Investigation", back_populates="game", uselist=False, cascade="all, delete-orphan"
    )
    batch_analysis: Mapped[Optional["BatchAnalysis"]] = relationship(
        "BatchAnalysis", back_populates="games", foreign_keys=[batch_id]
    )


class EngineEvaluation(Base):
    __tablename__ = "engine_evaluations_v2"

    id: Mapped[int] = Column(Integer, primary_key=True)
    game_id: Mapped[int] = Column(Integer, ForeignKey("games_v3.id"), nullable=False, index=True)
    move_number: Mapped[int] = Column(Integer, nullable=False)
    evaluation_cp: Mapped[float] = Column(Float, nullable=False)
    best_move: Mapped[Optional[str]] = Column(String(16))
    accuracy: Mapped[Optional[float]] = Column(Float)
    flagged: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    extra_metadata: Mapped[Optional[dict]] = Column(JSON)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    game: Mapped[Game] = relationship("Game", back_populates="evaluations")


class Investigation(Base):
    __tablename__ = "investigations_v2"

    id: Mapped[int] = Column(Integer, primary_key=True)
    game_id: Mapped[int] = Column(Integer, ForeignKey("games_v3.id"), nullable=False, unique=True)
    status: Mapped[InvestigationStatus] = Column(
        Enum(InvestigationStatus), default=InvestigationStatus.PENDING, nullable=False
    )
    summary: Mapped[Optional[str]] = Column(String(512))
    details: Mapped[Optional[dict]] = Column(JSON)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    game: Mapped[Game] = relationship("Game", back_populates="investigation")




class PlayerSnapshot(Base):
    """Historical snapshot of player metrics for trend analysis."""
    __tablename__ = "player_snapshots"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    username: Mapped[str] = Column(String(255), nullable=False, index=True)
    platform: Mapped[str] = Column(String(32), nullable=False)  # "lichess" or "chesscom"
    recorded_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Rating data
    rating: Mapped[Optional[int]] = Column(Integer)
    rating_type: Mapped[Optional[str]] = Column(String(32))  # "blitz", "rapid", "bullet"
    
    # Performance metrics
    games_analyzed: Mapped[int] = Column(Integer, default=0, nullable=False)
    avg_accuracy: Mapped[float] = Column(Float, default=0.0, nullable=False)
    avg_engine_agreement: Mapped[float] = Column(Float, default=0.0, nullable=False)
    avg_suspicion_score: Mapped[float] = Column(Float, default=0.0, nullable=False)
    flagged_games_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    
    # Trend indicators
    accuracy_trend: Mapped[Optional[str]] = Column(String(16))  # "improving", "stable", "declining"
    anomaly_detected: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    anomaly_reason: Mapped[Optional[str]] = Column(String(255))




# -----------------------------
# Pydantic response models
# -----------------------------


class EngineEvaluationRead(BaseModel):
    id: int
    move_number: int
    evaluation_cp: float = Field(..., description="Centipawn evaluation")
    best_move: Optional[str]
    accuracy: Optional[float]
    flagged: bool

    class Config:
        from_attributes = True


class InvestigationRead(BaseModel):
    id: int
    status: InvestigationStatus
    summary: Optional[str]
    details: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserRead(BaseModel):
    id: int
    username: str
    lichess_username: Optional[str]

    class Config:
        from_attributes = True


class GameRead(BaseModel):
    id: int
    lichess_id: str
    played_at: Optional[datetime]
    result: Optional[str]
    analysis_status: InvestigationStatus
    white_player: UserRead
    black_player: UserRead
    investigation: Optional[InvestigationRead]
    evaluations: List[EngineEvaluationRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


class GameImportRequest(BaseModel):
    lichess_id: str = Field(..., example="Q7h6s3KD", description="ID or external ID of the game")
    source: str = Field("lichess", description="Source platform (lichess, chesscom, etc)")
    pgn: Optional[str] = Field(None, description="PGN text if available")
    force: bool = Field(False, description="If true, reanalyse even if an analysis already exists")


class InvestigationFilter(BaseModel):
    status: Optional[InvestigationStatus] = None


class BatchAnalysisRequest(BaseModel):
    """Request to start a batch analysis."""
    source: str = Field(..., description="Platform: 'lichess' or 'chesscom'")
    username: str = Field(..., description="Username to analyze")
    timeframe: str = Field("1m", description="Timeframe window (1m, 3m, 6m, 12m, all)")


class BatchAnalysisRead(BaseModel):
    """Response for batch analysis status."""
    id: int
    source: str
    username: str
    total_games: int
    analyzed_count: int
    flagged_count: int
    reported_count: int
    avg_suspicion: float
    risk_level: Optional[str]
    
    # Streak Improbability fields
    longest_win_streak: int = 0
    streak_improbability_score: float = 0.0
    suspicious_streak_count: int = 0
    max_streak_improbability: float = 0.0
    
    status: str
    timeframe: Optional[str] = "1m"
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class FlaggedGameSummary(BaseModel):
    """COA-style summary for a flagged game."""
    game_id: int
    lichess_id: str
    source: str
    white: str
    black: str
    result: Optional[str]
    played_at: Optional[datetime]
    suspicion_score: float
    engine_agreement: float
    tom_score: float
    tension_complexity: float
    recommendation: str
    reference_game_id: Optional[str] = None # For comparison reporting
    reported: bool = False
    
    # V2 Metrics
    sniper_gap: float = 0.0
    streak_density: float = 0.0
    critical_accuracy: float = 0.0
    normal_accuracy: float = 0.0
