
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from server.services.analysis import GameAnalysisPipeline

DATA_DIR = Path(__file__).parent.parent / "data"
GAMES_DIR = DATA_DIR / "gm_games"

def ingest_games():
    db = SessionLocal()
    pipeline = GameAnalysisPipeline(db)
    
    # Files to ingest
    files = list(GAMES_DIR.glob("*.json"))
    
    print(f"Found {len(files)} game files to ingest from {GAMES_DIR}.")
    
    count = 0
    errors = 0
    
    for file_path in files:
        print(f"Processing {file_path.name}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                games = json.load(f)
                
            print(f"  Found {len(games)} games in file.")
            
            for game_data in games:
                try:
                    # Extract PGN and ID
                    pgn = game_data.get("pgn")
                    if not pgn:
                        continue
                        
                    # Determine ID / Source
                    url = game_data.get("url", "")
                    game_id = ""
                    source = "unknown"
                    
                    if "chess.com" in url:
                        source = "chesscom"
                        game_id = url.split("/")[-1]
                    elif "lichess.org" in url:
                        source = "lichess"
                        game_id = url.split("/")[-1][:8]
                    else:
                        game_id = f"import_{hash(pgn)}"
                        
                    pipeline.ingest_game(
                        lichess_id=game_id, 
                        pgn_text=pgn,
                        source=source,
                        force=False 
                    )
                    count += 1
                        
                except Exception as e:
                    errors += 1
                    
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            
    db.commit()
    db.close()
    print(f"\nDone! Ingested {count} games. Errors: {errors}")

if __name__ == "__main__":
    ingest_games()
