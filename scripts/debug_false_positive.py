
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from server.database import SessionLocal
from server.models.game import Game, User

async def debug_game():
    db = SessionLocal()
    
    # Andrew Tang's flagged game
    game_id = "import_3322357301613095524"
    
    game = db.execute(select(Game).where(Game.lichess_id == game_id)).scalar_one_or_none()
    if not game:
        print("Game not found!")
        return


    inv = game.investigation
    if not inv or not inv.details:
        print("Details missing, running analysis...")
        from server.services.analysis import GameAnalysisPipeline
        pipeline = GameAnalysisPipeline(db)
        game = pipeline.run_analysis(game.id, force=True)
        inv = game.investigation

    details = inv.details if inv and inv.details else {}
    if not details:
        print("No investigation details found.")
        return 
        
    print(f"Suspicion Score: {details.get('suspicion_score')}")
    print(f"Flags: {details.get('flags')}")
    
    details = inv.details
    print("\nMETRICS:")
    print(f"  Critical Gap: {details.get('critical_vs_normal_gap')}")
    print(f"  Critical Acc: {details.get('critical_moves_correct')}/{details.get('critical_moves_total')}")
    print(f"  Normal Acc:   {details.get('normal_moves_correct')}/{details.get('normal_moves_total')}")
    
    # print raw detections
    pass

if __name__ == "__main__":
    asyncio.run(debug_game())
