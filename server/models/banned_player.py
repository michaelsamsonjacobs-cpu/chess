from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint
from server.database import Base

class BannedPlayer(Base):
    """Known banned/cheating players from various platforms."""
    __tablename__ = "banned_players"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False, index=True)
    platform = Column(String(32), nullable=False)  # "lichess" or "chesscom"
    
    # Ban details
    ban_date = Column(DateTime(timezone=True))
    ban_type = Column(String(64), nullable=False)  # "tos_violation", "fair_play", "manual"
    ban_reason = Column(String(255))
    
    # Metadata
    source = Column(String(64), nullable=False)  # "lichess_api", "manual", "csv_import"
    first_seen = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_verified = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)  # Still banned?
    
    # Unique constraint on username + platform
    __table_args__ = (UniqueConstraint("username", "platform", name="uq_banned_player"),)
