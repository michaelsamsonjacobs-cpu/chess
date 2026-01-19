"""Player model for persistent investigation history."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, relationship

from server.database import Base


class Player(Base):
    """Persistent player record for history tracking."""
    __tablename__ = "players"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    platform: Mapped[str] = Column(String(32), nullable=False)  # "lichess" or "chesscom"
    username: Mapped[str] = Column(String(255), nullable=False, index=True)
    
    # Player info from platform API
    title: Mapped[Optional[str]] = Column(String(10))  # GM, IM, FM, etc.
    rating: Mapped[Optional[int]] = Column(Integer)
    status: Mapped[Optional[str]] = Column(String(32))  # active/closed/violated
    is_cheater_marked: Mapped[bool] = Column(Boolean, default=False)
    
    # Analysis tracking
    last_analyzed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))
    last_game_date: Mapped[Optional[datetime]] = Column(DateTime(timezone=True))  # For incremental updates
    total_games_analyzed: Mapped[int] = Column(Integer, default=0)
    total_analyses_count: Mapped[int] = Column(Integer, default=0)
    
    # Aggregated metrics from all analyses
    latest_risk_level: Mapped[Optional[str]] = Column(String(16))
    latest_avg_suspicion: Mapped[float] = Column(Float, default=0.0)
    total_flagged_games: Mapped[int] = Column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on platform + username
    __table_args__ = (
        # UniqueConstraint('platform', 'username', name='uq_player_platform_username'),
    )

    # Note: Relationship to BatchAnalysis would be added when we update that model
