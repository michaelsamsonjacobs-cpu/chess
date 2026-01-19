
import asyncio
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_warehouse.database import get_session
from data_warehouse.models import TrainingGame
from data_warehouse.adapters.chesscom_adapter import ChessComAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
LOGGER = logging.getLogger(__name__)

# Config
TITLES = ['GM', 'IM', 'FM', 'CM', 'NM'] # Limit to main titles for speed
PLAYERS_PER_TITLE = 3
GAMES_PER_PLAYER = 5 # Brief sample for immediate re-training

async def main():
    LOGGER.info("Starting Titled Player Ingestion...")
    adapter = ChessComAdapter()
    
    with get_session() as session:
        total_new = 0
        
        for title in TITLES:
            LOGGER.info(f"\n--- Processing Title: {title} ---")
            players = await adapter.get_titled_players(title)
            
            if not players:
                LOGGER.warning(f"No players found for {title}")
                continue
                
            LOGGER.info(f"Found {len(players)} {title} players total.")
            
            # Select random sample
            sample = random.sample(players, min(len(players), PLAYERS_PER_TITLE))
            
            for user in sample:
                LOGGER.info(f"  Fetching games for {user} ({title})...")
                count = 0
                
                try:
                    async for game in adapter.fetch_games(username=user, limit=GAMES_PER_PLAYER):
                        # check dupe
                        exists = session.query(TrainingGame).filter(TrainingGame.source_game_id == game.source_id).first()
                        if not exists:
                            tg = TrainingGame(
                                source="chesscom",
                                source_game_id=game.source_id,
                                pgn=game.pgn,
                                white_username=game.white_username,
                                black_username=game.black_username,
                                white_rating=game.white_rating,
                                black_rating=game.black_rating,
                                game_date=game.game_date,
                                time_class=game.time_class,
                                cheater_side='none', # Assuming clean for baseline
                                analyzed=False
                            )
                            session.add(tg)
                            count += 1
                    
                    session.commit()
                    LOGGER.info(f"    Saved {count} new games.")
                    total_new += count
                    
                except Exception as e:
                    LOGGER.error(f"    Failed to fetch for {user}: {e}")
                    
        LOGGER.info(f"\nIngestion Complete. Added {total_new} games.")

if __name__ == "__main__":
    asyncio.run(main())
