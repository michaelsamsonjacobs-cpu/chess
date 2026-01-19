
import asyncio
import logging
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_warehouse.database import get_session
from data_warehouse.models import TrainingGame
from data_warehouse.adapters.chesscom_adapter import ChessComAdapter

logging.basicConfig(level=logging.INFO, format='%(message)s')
LOGGER = logging.getLogger(__name__)

async def main(username, limit):
    LOGGER.info(f"Ingesting {limit} games for player: {username}...")
    adapter = ChessComAdapter()
    
    with get_session() as session:
        count = 0
        try:
            async for game in adapter.fetch_games(username=username, limit=limit):
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
                        cheater_side='none', # Mark as clean for baseline
                        analyzed=False
                    )
                    session.add(tg)
                    count += 1
            
            session.commit()
            LOGGER.info(f"Successfully saved {count} new games for {username}.")
            
        except Exception as e:
            LOGGER.error(f"Failed to fetch for {username}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument("--limit", type=int, default=20, help="Number of games")
    args = parser.parse_args()
    
    asyncio.run(main(args.username, args.limit))
