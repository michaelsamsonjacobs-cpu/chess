"""
Ingest "clean" GM games into the training warehouse.

Source: data/gm_games/*.json
Labels: non-cheater
"""

import logging
import json
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_warehouse.database import init_db, get_session
from data_warehouse.models import TrainingGame, DataSource, CheaterSide, CheaterType

def load_games(data_dir: Path) -> list:
    games = []
    json_files = list(data_dir.glob("*.json"))
    
    for json_file in json_files:
        LOGGER.info(f"Loading {json_file.name}...")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                # Handle different formats (list vs dict)
                if isinstance(content, list):
                    file_games = content
                elif isinstance(content, dict):
                    # Check if it has 'games' key
                    file_games = content.get('games', [])
                    # Or maybe it's a single game?
                    if not file_games and 'id' in content:
                        file_games = [content]
                else:
                    file_games = []
                    
                games.extend(file_games)
                LOGGER.info(f"  Loaded {len(file_games)} games")
        except Exception as e:
            LOGGER.error(f"  Failed: {e}")
            
    return games

def main():
    init_db()
    data_dir = Path(__file__).parent.parent / "data" / "gm_games"
    
    games = load_games(data_dir)
    LOGGER.info(f"Total clean games found: {len(games)}")
    
    with get_session() as session:
        inserted = 0
        for g in games:
            try:
                # Extract fields (assuming Lichess JSON format)
                game_id = g.get('id', '')
                if not game_id: continue
                
                players = g.get('players', {})
                white = players.get('white', {}).get('user', {}).get('name', 'unknown')
                black = players.get('black', {}).get('user', {}).get('name', 'unknown')
                
                # Check duplicate
                exists = session.query(TrainingGame).filter_by(source_game_id=game_id).first()
                if exists: continue
                
                tg = TrainingGame(
                    source=DataSource.LICHESS.value,
                    source_game_id=str(game_id),
                    pgn=g.get('pgn', ''), # Assuming 'moves' or we construct PGN. 
                    # Note: If JSON has 'moves' but not 'pgn', we might need to construct it. 
                    # Lichess JSON usually has 'moves'. For this MVP, let's assume 'pgn' key exists or we use 'moves' string.
                    white_username=white,
                    black_username=black,
                    white_rating=players.get('white', {}).get('rating'),
                    black_rating=players.get('black', {}).get('rating'),
                    cheater_side=CheaterSide.NONE.value,
                    cheater_type=CheaterType.UNKNOWN.value,
                    ban_confirmed=False,
                    ingested_at=datetime.utcnow()
                )
                
                # Fallback for PGN if missing
                if not tg.pgn:
                     tg.pgn = g.get('moves', '')
                
                session.add(tg)
                inserted += 1
                
                if inserted % 100 == 0:
                    session.commit()
            except Exception as e:
                LOGGER.error(f"Error inserting: {e}")
        
        session.commit()
        LOGGER.info(f"Ingested {inserted} clean games")

if __name__ == "__main__":
    main()
