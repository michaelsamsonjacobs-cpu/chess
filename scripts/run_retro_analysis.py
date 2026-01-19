
import asyncio
import os
import sys
from typing import List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from server.database import SessionLocal
from server.models.game import Game, User
from server.services.analysis import GameAnalysisPipeline

async def run_retro_analysis():
    db = SessionLocal()
    pipeline = GameAnalysisPipeline(db)
    
    # Target specific known cheaters for validation
    targets = ["ammarkefi", "tigranlpetrosyan", "brauliocuarta", "bigmak2500", "brizuelaronald"]
    
    print(f"🎯 Starting V2 Retro-Analysis on {len(targets)} targets...")
    
    try:
        for username in targets:
            # Get user
            user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if not user:
                print(f"⚠️ User {username} not found in DB.")
                continue
                
            # Get games
            games = db.execute(
                select(Game).where(Game.white_id == user.id)
            ).scalars().all()
            
            # Add black games too
            games_black = db.execute(
                select(Game).where(Game.black_id == user.id)
            ).scalars().all()
            
            all_games = list(set(games + games_black))
            
            print(f"\n🔍 Analyzing {len(all_games)} games for {username}...")
            
            suspect_count = 0
            sniper_count = 0
            
            for i, game in enumerate(all_games[:10]): # Limit to 10 games per player for speed
                print(f"  [{i+1}/{min(10, len(all_games))}] Re-analyzing Game {game.lichess_id}...", end="", flush=True)
                
                try:
                    # force=True triggers re-analysis with new V2 logic (MultiPV + Ensemble)
                    updated_game = pipeline.run_analysis(game.id, force=True)
                    
                    # Check results
                    inv = updated_game.investigation
                    if inv:
                        flags = inv.details.get("flags", [])
                        print(f" DONE. Score: {inv.details.get('suspicion_score')}")
                        if flags:
                            print(f"    🚩 Flags: {flags}")
                            suspect_count += 1
                            if any("SNIPER" in f for f in flags):
                                sniper_count += 1
                                
                except Exception as e:
                    print(f" ERROR: {e}")
            
            print(f"📊 Results for {username}: {suspect_count} flagged, {sniper_count} identified as SNIPERS.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_retro_analysis())
