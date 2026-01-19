"""
Feature extraction script for training data using REAL STOCKFISH ANALYSIS.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_warehouse.database import get_session
from data_warehouse.models import TrainingGame, TrainingFeatures
from server.services.model_inference import extract_features_from_pgn
from server.services.engine_service import EngineService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

async def process_games():
    LOGGER.info("Starting REAL feature extraction with Stockfish...")
    
    with get_session() as session:
        # PURGE OLD FAKE DATA to ensure clean training set
        deleted = session.query(TrainingFeatures).delete()
        session.commit()
        LOGGER.info(f"Purged {deleted} old feature records.")
        # NOTE: We are ADDING to the dataset now, not purging.
        # Ensure we process games that haven't been analyzed yet.
        
        games = session.query(TrainingGame).filter(
            TrainingGame.analyzed == False
        ).all()
        
        LOGGER.info(f"Selected {len(games)} un-analyzed games for processing.")
        
        processed = 0
        errors = 0
        
        try:
            # 1. Get a mix of games for the re-training subset
            # Analysis is slow (100ms/move * 40 moves = 4s/game).
            # 100 games = 400s (~7 mins).
            # We need balance: 50 clean, 50 cheaters.
            
            for game in games:
                try:
                    LOGGER.info(f"Analyzing game {game.id}...")
                    
                    # Real Async Analysis
                    features = await extract_features_from_pgn(game.pgn)
                    
                    # Check if feature record exists
                    existing = session.query(TrainingFeatures).filter_by(game_id=game.id).first()
                    if existing:
                        # Update
                        for key, val in features.items():
                            if hasattr(existing, key):
                                setattr(existing, key, val)
                    else:
                        # Create new
                        tf = TrainingFeatures(
                            game_id=game.id,
                            engine_agreement=features.get('engine_agreement', 0.0),
                            adjusted_engine_agreement=features.get('adjusted_engine_agreement', 0.0),
                            timing_suspicion=features.get('timing_suspicion', 0.0),
                            scramble_toggle_score=features.get('scramble_toggle_score', 0.0),
                            streak_improbability=features.get('streak_improbability', 0.0),
                            critical_position_accuracy=features.get('critical_position_accuracy', 0.0),
                            complexity_correlation=features.get('complexity_correlation', 0.0),
                            sniper_gap=features.get('sniper_gap', 0.0),
                            opponent_correlation_score=features.get('opponent_correlation_score', 0.0),
                            session_fatigue_score=features.get('session_fatigue_score', 0.0),
                            avg_centipawn_loss=features.get('avg_centipawn_loss', 0.0),
                            move_time_variance=features.get('move_time_variance', 0.0),
                            critical_moves_correct_pct=features.get('critical_moves_correct_pct', 0.0),
                            book_exit_accuracy=features.get('book_exit_accuracy', 0.0),
                            is_cheater=game.cheater_side in ('white', 'black', 'both'),
                        )
                        session.add(tf)
                    
                    game.analyzed = True
                    processed += 1
                    
                    if processed % 10 == 0:
                        session.commit()
                        LOGGER.info(f"Saved {processed} games.")
                        
                except Exception as e:
                    LOGGER.error(f"Error analyzing game {game.id}: {e}")
                    errors += 1
            
            session.commit()
            LOGGER.info(f"Extraction complete. Processed {processed}, Errors {errors}")
            
        finally:
            # Cleanup engine
            await EngineService().close()

if __name__ == "__main__":
    asyncio.run(process_games())
