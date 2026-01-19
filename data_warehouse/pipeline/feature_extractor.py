"""Feature extraction for training data.

Extracts the 15 detection signals from games for ML training.
Integrates with existing ChessGuard analysis services.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import io

import chess
import chess.pgn

# Try to import existing ChessGuard services
try:
    from server.services.engine import EngineRunner
    from server.services.timing_analysis import analyze_timing_patterns
    from server.services.complexity_analysis import calculate_position_complexity
    from server.services.advanced_detection import (
        calculate_sniper_detection,
        calculate_scramble_toggle
    )
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

from ..models import TrainingFeatures

LOGGER = logging.getLogger(__name__)


@dataclass
class ExtractedFeatures:
    """Raw extracted features before database storage."""
    # Core signals
    engine_agreement: float = 0.0
    adjusted_engine_agreement: float = 0.0
    timing_suspicion: float = 0.0
    scramble_toggle_score: float = 0.0
    streak_improbability: float = 0.0
    critical_position_accuracy: float = 0.0
    complexity_correlation: float = 0.0
    sniper_gap: float = 0.0
    opponent_correlation_score: float = 0.0
    session_fatigue_score: float = 0.0
    
    # Additional features
    avg_centipawn_loss: float = 0.0
    move_time_variance: float = 0.0
    critical_moves_correct_pct: float = 0.0
    book_exit_accuracy: float = 0.0
    total_moves: int = 0
    blunder_count: int = 0
    
    def to_training_features(self, game_id: int, is_cheater: bool) -> TrainingFeatures:
        """Convert to database model."""
        return TrainingFeatures(
            game_id=game_id,
            engine_agreement=self.engine_agreement,
            adjusted_engine_agreement=self.adjusted_engine_agreement,
            timing_suspicion=self.timing_suspicion,
            scramble_toggle_score=self.scramble_toggle_score,
            streak_improbability=self.streak_improbability,
            critical_position_accuracy=self.critical_position_accuracy,
            complexity_correlation=self.complexity_correlation,
            sniper_gap=self.sniper_gap,
            opponent_correlation_score=self.opponent_correlation_score,
            session_fatigue_score=self.session_fatigue_score,
            avg_centipawn_loss=self.avg_centipawn_loss,
            move_time_variance=self.move_time_variance,
            critical_moves_correct_pct=self.critical_moves_correct_pct,
            book_exit_accuracy=self.book_exit_accuracy,
            total_moves=self.total_moves,
            blunder_count=self.blunder_count,
            is_cheater=is_cheater,
        )


class FeatureExtractor:
    """Extracts ML features from chess games.
    
    Uses existing ChessGuard services when available, otherwise
    provides simplified extraction for basic features.
    """
    
    def __init__(
        self, 
        engine_path: Optional[str] = None,
        engine_depth: int = 16,
        use_engine: bool = True
    ):
        """Initialize feature extractor.
        
        Args:
            engine_path: Path to Stockfish binary
            engine_depth: Analysis depth
            use_engine: Whether to use engine analysis (slower but more accurate)
        """
        self.engine_path = engine_path
        self.engine_depth = engine_depth
        self.use_engine = use_engine and SERVICES_AVAILABLE
        self._engine = None
    
    def extract(
        self, 
        pgn: str, 
        cheater_side: str = "none",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExtractedFeatures:
        """Extract features from a PGN game.
        
        Args:
            pgn: PGN string of the game
            cheater_side: Which side is the cheater ('white', 'black', 'none')
            metadata: Optional additional metadata
            
        Returns:
            ExtractedFeatures object
        """
        features = ExtractedFeatures()
        
        try:
            game = chess.pgn.read_game(io.StringIO(pgn))
            if not game:
                LOGGER.warning("Failed to parse PGN")
                return features
            
            # Extract basic features without engine
            features = self._extract_basic_features(game, cheater_side)
            
            # Extract engine-based features if available
            if self.use_engine:
                features = self._extract_engine_features(game, cheater_side, features)
            
        except Exception as e:
            LOGGER.error(f"Error extracting features: {e}")
        
        return features
    
    def _extract_basic_features(
        self, 
        game: chess.pgn.Game,
        cheater_side: str
    ) -> ExtractedFeatures:
        """Extract features that don't require engine analysis."""
        features = ExtractedFeatures()
        
        board = game.board()
        moves = list(game.mainline_moves())
        features.total_moves = len(moves)
        
        # Extract timing from clock comments
        move_times = self._extract_move_times(game)
        if move_times:
            # Calculate timing statistics
            cheater_times = []
            for i, time in enumerate(move_times):
                is_cheater_move = (i % 2 == 0 and cheater_side == "white") or \
                                 (i % 2 == 1 and cheater_side == "black")
                if is_cheater_move:
                    cheater_times.append(time)
            
            if cheater_times:
                import statistics
                mean_time = statistics.mean(cheater_times)
                if mean_time > 0:
                    features.move_time_variance = statistics.stdev(cheater_times) / mean_time if len(cheater_times) > 1 else 0
                
                # Low variance with fast times is suspicious
                if features.move_time_variance < 0.3 and mean_time < 5:
                    features.timing_suspicion = 0.7
        
        return features
    
    def _extract_engine_features(
        self, 
        game: chess.pgn.Game,
        cheater_side: str,
        features: ExtractedFeatures
    ) -> ExtractedFeatures:
        """Extract features using engine analysis."""
        if not SERVICES_AVAILABLE:
            return features
        
        try:
            # This would integrate with existing GameAnalysisPipeline
            # For now, return basic features
            pass
        except Exception as e:
            LOGGER.warning(f"Engine analysis failed: {e}")
        
        return features
    
    def _extract_move_times(self, game: chess.pgn.Game) -> List[float]:
        """Extract move times from clock comments in PGN."""
        times = []
        node = game
        prev_clock = None
        
        while node.variations:
            node = node.variations[0]
            comment = node.comment or ""
            
            # Parse clock annotation [%clk H:MM:SS]
            import re
            match = re.search(r'\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]', comment)
            if match:
                hours, minutes, seconds = match.groups()
                clock = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                
                if prev_clock is not None:
                    time_taken = prev_clock - clock
                    if time_taken >= 0:
                        times.append(time_taken)
                
                prev_clock = clock
        
        return times
    
    def batch_extract(
        self, 
        games: List[Dict[str, Any]],
        parallel: bool = False
    ) -> List[ExtractedFeatures]:
        """Extract features from multiple games.
        
        Args:
            games: List of dicts with 'pgn' and 'cheater_side' keys
            parallel: Whether to use parallel processing
            
        Returns:
            List of ExtractedFeatures
        """
        results = []
        
        for game_data in games:
            pgn = game_data.get("pgn", "")
            cheater_side = game_data.get("cheater_side", "none")
            metadata = game_data.get("metadata")
            
            features = self.extract(pgn, cheater_side, metadata)
            results.append(features)
        
        return results


def extract_features_for_game(
    session,
    game_id: int,
    extractor: Optional[FeatureExtractor] = None
) -> Optional[TrainingFeatures]:
    """Extract and store features for a training game.
    
    Args:
        session: Database session
        game_id: ID of the training game
        extractor: Optional pre-configured extractor
        
    Returns:
        TrainingFeatures record or None if extraction failed
    """
    from ..models import TrainingGame
    
    game = session.query(TrainingGame).filter_by(id=game_id).first()
    if not game:
        LOGGER.warning(f"Game {game_id} not found")
        return None
    
    if extractor is None:
        extractor = FeatureExtractor(use_engine=False)
    
    features = extractor.extract(game.pgn, game.cheater_side or "none")
    
    is_cheater = game.cheater_side in ("white", "black", "both")
    db_features = features.to_training_features(game_id, is_cheater)
    
    session.add(db_features)
    game.analyzed = True
    
    return db_features
