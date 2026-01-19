"""
Ingest existing cheater game data into the training warehouse.

This script:
1. Loads games from data/cheater_games/*.json
2. Inserts them into the TrainingGame table
3. Marks them with appropriate cheater labels
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_warehouse.database import init_db, get_session
from data_warehouse.models import TrainingGame, DataSource, CheaterSide, CheaterType


def load_cheater_games(data_dir: Path) -> list:
    """Load all cheater game files from the data directory."""
    games = []
    json_files = list(data_dir.glob("*.json"))
    
    LOGGER.info(f"Found {len(json_files)} cheater game files")
    
    for json_file in json_files:
        username = json_file.stem.replace("chesscom_", "")
        LOGGER.info(f"Loading games from {json_file.name}...")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle different JSON structures
            if isinstance(data, list):
                file_games = data
            elif isinstance(data, dict) and 'games' in data:
                file_games = data['games']
            else:
                file_games = [data]
            
            for game in file_games:
                game['_cheater_username'] = username
                games.append(game)
                
            LOGGER.info(f"  Loaded {len(file_games)} games for {username}")
            
        except Exception as e:
            LOGGER.error(f"  Failed to load {json_file.name}: {e}")
            continue
    
    return games


def create_training_game(game_data: dict, cheater_username: str) -> TrainingGame:
    """Convert raw game data to TrainingGame model."""
    
    # Get PGN
    pgn = game_data.get('pgn', '')
    
    # Determine which side the cheater was playing
    white = game_data.get('white', {})
    black = game_data.get('black', {})
    
    white_username = white.get('username', '') if isinstance(white, dict) else str(white)
    black_username = black.get('username', '') if isinstance(black, dict) else str(black)
    
    if cheater_username.lower() == white_username.lower():
        cheater_side = CheaterSide.WHITE
    elif cheater_username.lower() == black_username.lower():
        cheater_side = CheaterSide.BLACK
    else:
        cheater_side = CheaterSide.UNKNOWN
    
    # Extract ratings
    white_rating = white.get('rating') if isinstance(white, dict) else None
    black_rating = black.get('rating') if isinstance(black, dict) else None
    
    # Get game URL as source_id
    source_id = game_data.get('url', game_data.get('id', str(hash(pgn))))
    
    # Parse time control
    time_control = game_data.get('time_control', game_data.get('time_class', ''))
    
    return TrainingGame(
        source=DataSource.CHESSCOM.value,
        source_game_id=str(source_id),
        pgn=pgn,
        white_username=white_username,
        black_username=black_username,
        white_rating=white_rating,
        black_rating=black_rating,
        time_control=str(time_control) if time_control else None,
        cheater_side=cheater_side.value,
        cheater_type=CheaterType.ENGINE_FULL.value,
        ban_confirmed=True,
    )


def main():
    """Main ingestion function."""
    
    # Initialize database
    LOGGER.info("Initializing training database...")
    init_db()
    
    # Path to cheater games
    data_dir = Path(__file__).parent.parent / "data" / "cheater_games"
    
    if not data_dir.exists():
        LOGGER.error(f"Data directory not found: {data_dir}")
        return
    
    # Load all games
    games = load_cheater_games(data_dir)
    LOGGER.info(f"Total games loaded: {len(games)}")
    
    if not games:
        LOGGER.warning("No games to ingest")
        return
    
    # Insert into database
    LOGGER.info("Inserting games into training database...")
    inserted = 0
    skipped = 0
    errors = 0
    
    with get_session() as session:
        for game_data in games:
            cheater_username = game_data.pop('_cheater_username', 'unknown')
            
            try:
                training_game = create_training_game(game_data, cheater_username)
                
                # Check for duplicate
                existing = session.query(TrainingGame).filter(
                    TrainingGame.source_game_id == training_game.source_game_id
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                session.add(training_game)
                inserted += 1
                
                # Commit in batches
                if inserted % 500 == 0:
                    session.commit()
                    LOGGER.info(f"  Inserted {inserted} games...")
                    
            except Exception as e:
                errors += 1
                if errors < 10:  # Only log first 10 errors
                    LOGGER.error(f"  Error inserting game: {e}")
                continue
        
        # Final commit
        session.commit()
    
    LOGGER.info("=" * 50)
    LOGGER.info(f"Ingestion complete!")
    LOGGER.info(f"  Inserted: {inserted}")
    LOGGER.info(f"  Skipped (duplicates): {skipped}")
    LOGGER.info(f"  Errors: {errors}")
    LOGGER.info("=" * 50)


if __name__ == "__main__":
    main()
