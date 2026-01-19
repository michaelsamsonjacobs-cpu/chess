"""Base adapter interface for data source ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncIterator

from ..models import TrainingGame, CheaterLabel


@dataclass
class RawGame:
    """Raw game data before normalization."""
    source_id: str
    pgn: str
    white_username: str
    black_username: str
    white_rating: Optional[int] = None
    black_rating: Optional[int] = None
    time_control: Optional[str] = None
    time_class: Optional[str] = None
    game_date: Optional[datetime] = None
    result: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseAdapter(ABC):
    """Abstract base class for data source adapters.
    
    Each adapter handles:
    1. Fetching raw games from its source
    2. Normalizing to unified schema
    3. Determining ground truth labels
    """
    
    source_name: str = "unknown"
    
    @abstractmethod
    async def fetch_games(self, limit: int = 1000, **kwargs) -> AsyncIterator[RawGame]:
        """Fetch raw games from the data source.
        
        Args:
            limit: Maximum number of games to fetch
            **kwargs: Source-specific parameters
            
        Yields:
            RawGame objects
        """
        pass
    
    @abstractmethod
    def get_cheater_label(self, raw: RawGame) -> CheaterLabel:
        """Determine the ground truth label for a game.
        
        Args:
            raw: Raw game data
            
        Returns:
            CheaterLabel with side, type, and confirmation status
        """
        pass
    
    def normalize(self, raw: RawGame, label: CheaterLabel) -> TrainingGame:
        """Convert raw game to unified TrainingGame schema.
        
        Args:
            raw: Raw game data
            label: Ground truth label
            
        Returns:
            TrainingGame ready for database insertion
        """
        return TrainingGame(
            source=self.source_name,
            source_game_id=raw.source_id,
            pgn=raw.pgn,
            white_username=raw.white_username,
            black_username=raw.black_username,
            white_rating=raw.white_rating,
            black_rating=raw.black_rating,
            cheater_side=label.side,
            cheater_type=label.cheater_type,
            ban_confirmed=label.confirmed,
            ban_date=label.ban_date,
            time_control=raw.time_control,
            time_class=raw.time_class,
            game_date=raw.game_date,
        )
    
    @abstractmethod
    async def discover_cheaters(self, limit: int = 100) -> List[str]:
        """Discover new cheater usernames from the source.
        
        Args:
            limit: Maximum number of cheaters to discover
            
        Returns:
            List of usernames identified as cheaters
        """
        pass
    
    async def ingest_batch(
        self, 
        session, 
        limit: int = 1000,
        **kwargs
    ) -> int:
        """Ingest a batch of games into the database.
        
        Args:
            session: Database session
            limit: Maximum games to ingest
            **kwargs: Source-specific parameters
            
        Returns:
            Number of games ingested
        """
        count = 0
        async for raw in self.fetch_games(limit=limit, **kwargs):
            label = self.get_cheater_label(raw)
            game = self.normalize(raw, label)
            session.add(game)
            count += 1
            
            # Commit in batches
            if count % 100 == 0:
                session.commit()
        
        session.commit()
        return count


class SyntheticAdapter(BaseAdapter):
    """Base class for synthetic/simulated data sources (e.g., Kaggle).
    
    These sources have pre-labeled data where cheating was simulated.
    """
    
    def __init__(self, data_path: str):
        self.data_path = data_path
    
    async def discover_cheaters(self, limit: int = 100) -> List[str]:
        """Synthetic data doesn't have real cheaters to discover."""
        return []


class PlatformAdapter(BaseAdapter):
    """Base class for real platform data sources (Lichess, Chess.com).
    
    These sources require API access and cheater discovery.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {"User-Agent": "ChessGuard/1.0 (research@chessguard.dev)"}
    
    def _classify_time_control(self, time_control: str) -> str:
        """Classify time control into bullet/blitz/rapid/classical."""
        if not time_control:
            return "unknown"
        
        # Parse time control (formats: "180" or "180+2" or "1/0")
        try:
            if "/" in time_control:
                # Correspondence format
                return "classical"
            
            parts = time_control.replace("+", " ").split()
            base_time = int(parts[0])
            increment = int(parts[1]) if len(parts) > 1 else 0
            
            # Estimated game duration = base + 40 * increment
            estimated = base_time + 40 * increment
            
            if estimated < 180:
                return "bullet"
            elif estimated < 600:
                return "blitz"
            elif estimated < 1800:
                return "rapid"
            else:
                return "classical"
        except (ValueError, IndexError):
            return "unknown"
