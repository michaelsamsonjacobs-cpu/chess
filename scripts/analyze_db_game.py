import asyncio
import logging
import sys
from pathlib import Path
import time
import io
import chess.pgn

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from server.services.model_inference import predict_cheating, extract_features_from_pgn
from data_warehouse.database import get_session
from data_warehouse.models import TrainingGame
from server.services.engine_service import EngineService

logging.basicConfig(level=logging.ERROR)

FEATURE_NAMES = [
    'engine_agreement', 'adjusted_engine_agreement', 'timing_suspicion', 
    'scramble_toggle_score', 'streak_improbability', 'critical_position_accuracy', 
    'complexity_correlation', 'sniper_gap', 'opponent_correlation_score', 
    'session_fatigue_score', 'avg_centipawn_loss', 'move_time_variance',
    'critical_moves_correct_pct', 'book_exit_accuracy'
]

async def analyze_cheater_sample():
    start_time = time.time()
    print(f"\n🔍 Analyzing 3 Random CHEATER Games from DB...")
    
    cheater_games = []
    
    with get_session() as session:
        # Get 3 random games marked as cheater
        from sqlalchemy.sql.expression import func
        games = session.query(TrainingGame).filter(
            TrainingGame.cheater_side != 'none'
        ).order_by(func.random()).limit(3).all()
        
        if not games:
            print("No cheater games found in DB.")
            return
            
        for game in games:
            cheater_games.append({
                'pgn': game.pgn,
                'game_id': game.source_game_id or str(game.id),
                'cheater_side': game.cheater_side,
                'white': game.white_username,
                'black': game.black_username
            })
        
    print(f"✅ Found {len(cheater_games)} cheater games. Running ML inference...\n")
    
    # Header
    print(f"{'Game ID':<25} | {'Risk Score':<10} | {'Time Var':<8} | {'Sniper':<8} | {'M-Strk':<6} | {'Comp Cor':<8} | {'CPL':<8}")
    print("-" * 120)
    print("-" * 115) 

    for cg in cheater_games:
        pgn = cg['pgn']
        game_id = cg['game_id']
        
        # Simulate game data dict for inference
        game_data = {"pgn": pgn}
        score, reason = await predict_cheating(game_data)
        
        # Get raw features
        features = await extract_features_from_pgn(pgn)
        
        # Determine color
        risk_color = ""
        if score > 0.8: risk_color = "🔴"
        elif score > 0.5: risk_color = "🟡"
        else: risk_color = "🟢"
        
        # Extract Display Metrics
        time_var = features.get('move_time_variance', 0.0)
        sniper = features.get('sniper_gap', 0.0)
        streak = features.get('streak_improbability', 0.0) * 10
        comp_corr = features.get('complexity_correlation', 0.0)
        avg_cpl = features.get('avg_centipawn_loss', 0.0)
        
        # Truncate game_id for display
        display_id = game_id[:22] if len(game_id) > 22 else game_id
        
        print(f"{display_id:<25} | {risk_color} {score:.1%}   | {time_var:.3f}    | {sniper:.3f}     | {streak:<6.1f} | {comp_corr:<8.3f} | {avg_cpl:<8.2f}")
        print(f"   ↳ Cheater: {cg['cheater_side'].upper()} | {cg['white']} vs {cg['black']}")
    
    print(f"\nTime taken: {time.time() - start_time:.2f}s")
    
    # Cleanup
    await EngineService().close()

if __name__ == "__main__":
    asyncio.run(analyze_cheater_sample())
