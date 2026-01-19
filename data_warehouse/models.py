"""SQLAlchemy models for the training data warehouse."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, 
    ForeignKey, JSON, Index, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class CheaterSide(str, Enum):
    """Which side was cheating in a game."""
    WHITE = "white"
    BLACK = "black"
    BOTH = "both"
    NONE = "none"


class CheaterType(str, Enum):
    """Type of cheating detected."""
    ENGINE_FULL = "engine_full"           # Used engine for all moves
    ENGINE_SELECTIVE = "engine_selective"  # Used engine for critical moments only
    SANDBAGGING = "sandbagging"           # Intentionally losing to lower rating
    BOOSTING = "boosting"                 # Colluding with another account
    UNKNOWN = "unknown"


class DataSource(str, Enum):
    """Source of the training data."""
    KAGGLE = "kaggle"
    LICHESS = "lichess"
    CHESSCOM = "chesscom"
    CRAWLED = "crawled"
    MANUAL = "manual"


class TrainingGame(Base):
    """Core game table with cheater labels for ML training."""
    
    __tablename__ = "training_games"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Source tracking
    source = Column(String(50), nullable=False, index=True)
    source_game_id = Column(String(100))
    
    # Game data
    pgn = Column(Text, nullable=False)
    
    # Player information
    white_username = Column(String(100))
    black_username = Column(String(100))
    white_rating = Column(Integer)
    black_rating = Column(Integer)
    
    # Labels (ground truth)
    cheater_side = Column(String(10), index=True)  # 'white', 'black', 'both', 'none'
    cheater_type = Column(String(50))              # 'engine_full', 'engine_selective', etc.
    ban_confirmed = Column(Boolean, default=False)
    ban_date = Column(DateTime)
    
    # Time control
    time_control = Column(String(50))
    time_class = Column(String(20))  # 'bullet', 'blitz', 'rapid', 'classical'
    
    # Pre-computed features (JSON for flexibility)
    features = Column(JSON)
    
    # Metadata
    game_date = Column(DateTime)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    analyzed = Column(Boolean, default=False)
    
    # Relationships
    training_features = relationship("TrainingFeatures", back_populates="game", uselist=False)
    
    def __repr__(self):
        return f"<TrainingGame {self.id}: {self.white_username} vs {self.black_username} ({self.source})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "white_username": self.white_username,
            "black_username": self.black_username,
            "white_rating": self.white_rating,
            "black_rating": self.black_rating,
            "cheater_side": self.cheater_side,
            "cheater_type": self.cheater_type,
            "ban_confirmed": self.ban_confirmed,
            "time_class": self.time_class,
            "game_date": self.game_date.isoformat() if self.game_date else None,
        }


class TrainingFeatures(Base):
    """Pre-computed feature vectors for ML training.
    
    These are the 15 detection signals normalized to 0-1 range,
    plus additional derived features useful for ML.
    """
    
    __tablename__ = "training_features"
    
    game_id = Column(Integer, ForeignKey("training_games.id"), primary_key=True)
    
    # Core detection signals (normalized 0-1)
    engine_agreement = Column(Float)
    adjusted_engine_agreement = Column(Float)
    timing_suspicion = Column(Float)
    scramble_toggle_score = Column(Float)
    streak_improbability = Column(Float)
    critical_position_accuracy = Column(Float)
    complexity_correlation = Column(Float)
    sniper_gap = Column(Float)
    opponent_correlation_score = Column(Float)
    session_fatigue_score = Column(Float)
    
    # Additional ML features
    avg_centipawn_loss = Column(Float)
    move_time_variance = Column(Float)
    critical_moves_correct_pct = Column(Float)
    book_exit_accuracy = Column(Float)
    total_moves = Column(Integer)
    blunder_count = Column(Integer)
    
    # Label (target variable)
    is_cheater = Column(Boolean, nullable=False, index=True)
    
    # Relationship
    game = relationship("TrainingGame", back_populates="training_features")
    
    def to_feature_vector(self) -> list:
        """Return features as a list for ML training."""
        return [
            self.engine_agreement or 0,
            self.adjusted_engine_agreement or 0,
            self.timing_suspicion or 0,
            self.scramble_toggle_score or 0,
            self.streak_improbability or 0,
            self.critical_position_accuracy or 0,
            self.complexity_correlation or 0,
            self.sniper_gap or 0,
            self.opponent_correlation_score or 0,
            self.session_fatigue_score or 0,
            self.avg_centipawn_loss or 0,
            self.move_time_variance or 0,
            self.critical_moves_correct_pct or 0,
            self.book_exit_accuracy or 0,
        ]
    
    @staticmethod
    def feature_names() -> list:
        """Return ordered list of feature names."""
        return [
            "engine_agreement",
            "adjusted_engine_agreement", 
            "timing_suspicion",
            "scramble_toggle_score",
            "streak_improbability",
            "critical_position_accuracy",
            "complexity_correlation",
            "sniper_gap",
            "opponent_correlation_score",
            "session_fatigue_score",
            "avg_centipawn_loss",
            "move_time_variance",
            "critical_moves_correct_pct",
            "book_exit_accuracy",
        ]


class CheaterLabel:
    """Helper class for labeling games during ingestion."""
    
    def __init__(
        self, 
        side: str = "none",
        cheater_type: str = "unknown",
        confirmed: bool = False,
        ban_date: Optional[datetime] = None
    ):
        self.side = side
        self.cheater_type = cheater_type
        self.confirmed = confirmed
        self.ban_date = ban_date
    
    @property
    def is_cheater(self) -> bool:
        return self.side in ("white", "black", "both")


# Create indexes for common queries
Index("idx_training_games_source_cheater", TrainingGame.source, TrainingGame.cheater_side)
Index("idx_training_games_time_class", TrainingGame.time_class)
