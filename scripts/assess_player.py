import asyncio
import logging
import sys
from pathlib import Path
import time
import io
import chess
import chess.pgn

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from server.services.model_inference import predict_cheating, extract_features_from_pgn
from data_warehouse.adapters.chesscom_adapter import ChessComAdapter
from server.services.engine_service import EngineService

logging.basicConfig(level=logging.ERROR)

FEATURE_NAMES = [
    'engine_agreement', 'adjusted_engine_agreement', 'timing_suspicion', 
    'scramble_toggle_score', 'streak_improbability', 'critical_position_accuracy', 
    'complexity_correlation', 'sniper_gap', 'opponent_correlation_score', 
    'session_fatigue_score', 'avg_centipawn_loss', 'move_time_variance',
    'critical_moves_correct_pct', 'book_exit_accuracy'
]

import random

async def analyze_player(username: str, limit: int = 20):
    start_time = time.time()
    print(f"\n🔍 Analyzing Player: {username}")
    print(f"   Strategy: Random sampling of recent WINS (to catch peak performance)")
    
    # 1. Fetch Games (Fetch more to get a good sample of wins, e.g. 50)
    fetch_limit = 50 
    try:
        print(f"   Fetching last {fetch_limit} games from Chess.com...")
        adapter = ChessComAdapter()
        all_games = []
        async for game in adapter.fetch_games(username=username, limit=fetch_limit):
             # We need to parse result to know if it's a win
             # But fetch_games returns an object where pgn is a string.
             # We can do a quick check on the PGN string or headers if parsed.
             # Ideally adapter returns metadata. For now, simple string check or lazy parse.
             all_games.append(game)
    except Exception as e:
        print(f"Error fetching games: {e}")
        return

    if not all_games:
        print("No games found.")
        return
        
    # 2. Filter for Wins
    winning_games = []
    for game in all_games:
        # Quick parse result
        if not game.pgn: continue
        
        # Determine color and result
        # This is a bit expensive to parse everything but necessary for filtering
        # We can do a lightweight string check first
        # [White "Username"] ... [Result "1-0"]
        pgn_lower = game.pgn.lower()
        is_white = f'[white "{username.lower()}"' in pgn_lower
        is_black = f'[black "{username.lower()}"' in pgn_lower
        
        if not is_white and not is_black:
            continue # Should not happen
            
        # Check result
        # We need accurate result parsing
        pgn_io = io.StringIO(game.pgn)
        headers = chess.pgn.read_headers(pgn_io)
        if not headers: continue
        
        result = headers.get("Result", "*")
        white_player = headers.get("White", "").lower()
        
        user_won = False
        if white_player == username.lower():
            if result == "1-0": user_won = True
        else:
            if result == "0-1": user_won = True
            
        if user_won:
            winning_games.append(game)
            
    print(f"✅ Found {len(all_games)} recent games. {len(winning_games)} are wins.")
    
    # 3. Random Sample
    sample_size = min(limit, len(winning_games))
    if sample_size == 0:
        print("❌ No wins found in recent games to analyze.")
        return
        
    games_list = random.sample(winning_games, sample_size)
    print(f"🎲 Randomly selected {len(games_list)} wins for deep analysis...\n")
    
    # Header
    print(f"{'Game ID':<15} | {'Risk Score':<10} | {'Time Var':<8} | {'Sniper':<8} | {'M-Strk':<6} | {'Comp Cor':<8} | {'Reason':<30}")
    print("-" * 115) 

    total_score = 0
    game_count = 0
    
    # Session Stats for "Digital Baseball Card"
    session_actual_score = 0.0
    session_expected_score = 0.0
    session_games_with_elo = 0
    
    for game in games_list:
        pgn = game.pgn
        if not pgn:
            continue
            
        # Simulate game data dict for inference
        game_data = {"pgn": pgn}
        score, reason = await predict_cheating(game_data)
        
        # Get raw features for detailed breakdown
        features = await extract_features_from_pgn(pgn)
        
        # Accumulate
        total_score += score
        game_count += 1
        
        # Determine color
        risk_color = ""
        if score > 0.8: risk_color = "🔴"
        elif score > 0.5: risk_color = "🟡"
        else: risk_color = "🟢"
        
        # Extract Display Metrics
        time_var = features.get('move_time_variance', 0.0)
        sniper = features.get('sniper_gap', 0.0)
        streak = features.get('streak_improbability', 0.0)
        comp_corr = features.get('complexity_correlation', 0.0)
        
        print(f"{game.source_id[:12]:<15} | {risk_color} {score:.1%}   | {time_var:.3f}    | {sniper:.3f}     | {streak:<6.1f} | {comp_corr:<8.3f} | {reason:<30}")

        # -------------------------------------------------------------------------
        # SESSION LOGIC: Expected vs Actual Score (Game Streak Improbability)
        # -------------------------------------------------------------------------
        try:
            # Re-parse PGN for headers
            pgn_io = io.StringIO(pgn)
            pgn_game = chess.pgn.read_game(pgn_io)
            
            if pgn_game and pgn_game.headers:
                # Determine user color
                user_color = None
                opponent_rating = 0
                user_rating = 0
                
                white = pgn_game.headers.get("White", "").lower()
                black = pgn_game.headers.get("Black", "").lower()
                
                if white == username.lower():
                    user_color = chess.WHITE
                    try: user_rating = int(pgn_game.headers.get("WhiteElo", 0))
                    except: pass
                    try: opponent_rating = int(pgn_game.headers.get("BlackElo", 0))
                    except: pass
                elif black == username.lower():
                    user_color = chess.BLACK
                    try: user_rating = int(pgn_game.headers.get("BlackElo", 0))
                    except: pass
                    try: opponent_rating = int(pgn_game.headers.get("WhiteElo", 0))
                    except: pass
                    
                # Determine Result
                result = pgn_game.headers.get("Result", "*")
                actual_points = 0.0
                if result == "1-0":
                    actual_points = 1.0 if user_color == chess.WHITE else 0.0
                elif result == "0-1":
                    actual_points = 1.0 if user_color == chess.BLACK else 0.0
                elif result == "1/2-1/2":
                    actual_points = 0.5
                    
                # Elo Expectation
                if user_rating and opponent_rating and (result in ["1-0", "0-1", "1/2-1/2"]):
                    expected_score = 1 / (1 + 10 ** ((opponent_rating - user_rating) / 400))
                    
                    session_actual_score += actual_points
                    session_expected_score += expected_score
                    session_games_with_elo += 1
                
        except Exception as e:
            pass # Skip if Elo parsing fails

    if game_count == 0:
        print("No valid games to analyze.")
        return

    # -------------------------------------------------------------------------
    # DIGITAL BASEBALL CARD (Player Summary)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"🃏 PLAYER CARD: {username.upper()}")
    print("=" * 60)
    
    avg_score = total_score / game_count
    verdict = "✅ CLEAN"
    verdict_color = "🟢"
    if avg_score > 0.5: 
        verdict = "⚠️ SUSPICIOUS"
        verdict_color = "🟡" 
    if avg_score > 0.8: 
        verdict = "⛔ CHEATING DETECTED"
        verdict_color = "🔴"
    
    print(f" OVERALL VERDICT:  {verdict_color} {verdict} ({avg_score:.1%} Risk)")
    print("-" * 60)
    
    print(f" 📈 PERFORMANCE STATS (Last {game_count} games)")
    if session_games_with_elo > 0:
        delta = session_actual_score - session_expected_score
        print(f" • Actual Score:   {session_actual_score} / {session_games_with_elo}")
        print(f" • Expected Score: {session_expected_score:.2f} (Elo-based)")
        print(f" • Overperform:    {delta:+.2f} pts {'⚠️ (Statistical Anomaly)' if delta > 2.0 else '✅ (Normal)'}")
    else:
        print(" • Elo data unavailable for streak analysis.")
    
    print("-" * 60)
    print(f" 🧠 BEHAVIORAL SIGNATURES")
    print(" • Time Variance:  (Wait for data...)") 
    
    print("\nDetailed analysis complete.")
    print(f"Time taken: {time.time() - start_time:.2f}s")
    
    # Cleanup
    await EngineService().close()

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "DanielNaroditsky"
    asyncio.run(analyze_player(username))
