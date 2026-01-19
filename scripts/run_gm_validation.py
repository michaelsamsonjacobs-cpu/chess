
import asyncio
import os
import sys
from typing import List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, or_
from server.database import SessionLocal
from server.models.game import Game, User
from server.services.analysis import GameAnalysisPipeline

async def run_gm_validation():
    db = SessionLocal()
    pipeline = GameAnalysisPipeline(db)
    
    # Validation Targets (Top GMs)
    targets = ["drnykterstein", "penguingim1", "rebeig", "hikaru", "magnuscarlsen"]
    
    print(f"👑 Starting GM Validation Run on {len(targets)} targets...")
    print("Goal: Confirm FALSE POSITIVE RATE is low (<5%).")
    
    total_games = 0
    total_flagged = 0
    total_snipers = 0
    
    try:
        for username in targets:
            user = db.execute(select(User).where(User.username == username.lower())).scalar_one_or_none()
            if not user:
                print(f"⚠️ User {username} not found in DB.")
                continue
                
            games = db.execute(
                select(Game).where(or_(Game.white_id == user.id, Game.black_id == user.id))
            ).scalars().all()
            
            print(f"\n🔍 Analyzing {len(games)} games for {username}...")
            
            player_flagged = 0
            
            # Analyze all available games (up to 20 for speed in this test)
            for i, game in enumerate(games[:20]): 
                print(f"  [{i+1}/{min(20, len(games))}] Analyzing Game {game.lichess_id}...", end="", flush=True)
                
                try:
                    updated_game = pipeline.run_analysis(game.id, force=True)
                    
                    inv = updated_game.investigation
                    score = inv.details.get('suspicion_score', 0)
                    flags = inv.details.get("flags", [])
                    
                    print(f" DONE. Score: {score}")
                    
                    if score > 0.5 or flags:
                        player_flagged += 1
                        total_flagged += 1
                        print(f"    🚨 FLAGGED: {flags} (Score: {score})")
                        if any("SNIPER" in f for f in flags):
                            total_snipers += 1
                    
                    total_games += 1
                                
                except Exception as e:
                    print(f" ERROR: {e}")
            
            print(f"📊 {username}: {player_flagged}/{min(20, len(games))} flagged.")

        print("\n" + "="*50)
        print("VALIDATION SUMMARY")
        print("="*50)
        print(f"Total Games Analyzed: {total_games}")
        print(f"Total Flagged: {total_flagged} ({total_flagged/total_games*100:.1f}%)")
        print(f"Total Snipers: {total_snipers}")
        
        if total_flagged / total_games < 0.1:
            print("✅ SUCCESS: False Positive Rate is acceptable.")
        else:
            print("❌ WARNING: High False Positive Rate!")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_gm_validation())
