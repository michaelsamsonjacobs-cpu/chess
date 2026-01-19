
import asyncio
import json
import chess
import chess.engine
import chess.pgn
import io
import sys
from pathlib import Path
from typing import Dict, List, Any

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
GAMES_DIR = DATA_DIR / "cheater_games"
RESULTS_FILE = DATA_DIR / "sniper_analysis_results.json"
BIN_DIR = Path(__file__).parent.parent / "bin" 
STOCKFISH_EXE = BIN_DIR / "stockfish-windows-x86-64-avx2.exe"

# Analysis Parameters
DEPTH = 12 # Fast but decent
CRITICAL_EVAL_DIFF = 0.75 # Pawn units diff between 1st and 2nd best
MAX_EVAL = 2.0 # Only consider positions that are relatively balanced/playable

async def analyze_game(engine: chess.engine.Protocol, pgn_text: str, username: str) -> Dict[str, Any]:
    pgn = io.StringIO(pgn_text)
    game = chess.pgn.read_game(pgn)
    if not game:
        return None
        
    board = game.board()
    
    # Identify player color
    white_player = game.headers.get("White", "").lower()
    player_color = chess.WHITE if white_player == username.lower() else chess.BLACK
    
    critical_moves_correct = 0
    critical_moves_total = 0
    normal_moves_correct = 0
    normal_moves_total = 0
    
    for move in game.mainline_moves():
        # Only analyze player's moves
        if board.turn == player_color:
            try:
                # Analyze position (MultiPV=2 to compare top moves)
                info = await engine.analyse(board, chess.engine.Limit(depth=DEPTH), multipv=2)
                
                if len(info) >= 2:
                    best_move = info[0]["pv"][0]
                    score1 = info[0]["score"].white().score(mate_score=10000)
                    score2 = info[1]["score"].white().score(mate_score=10000)
                    
                    # Convert to pawns (roughly)
                    eval1 = score1 / 100.0
                    eval2 = score2 / 100.0
                    
                    # Abs eval (from perspective of side to move?)
                    # score() returns white perspective.
                    # if black to move, low score is good.
                    # Let's just use abs diff.
                    
                    diff = abs(eval1 - eval2)
                    
                    # Check if position is balanced enough to be "critical" (not already +5 winning)
                    is_balanced = abs(eval1) < MAX_EVAL
                    
                    is_critical = is_balanced and diff > CRITICAL_EVAL_DIFF
                    
                    played_best = (move == best_move)
                    
                    if is_critical:
                        critical_moves_total += 1
                        if played_best:
                            critical_moves_correct += 1
                    else:
                        normal_moves_total += 1
                        if played_best:
                            normal_moves_correct += 1
                            
            except Exception as e:
                # print(f"Error analyzing move: {e}")
                pass
                
        board.push(move)
        
    return {
        "critical_total": critical_moves_total,
        "critical_correct": critical_moves_correct,
        "normal_total": normal_moves_total,
        "normal_correct": normal_moves_correct
    }

async def processing_loop():
    if not STOCKFISH_EXE.exists():
        print(f"Error: Stockfish not found at {STOCKFISH_EXE}")
        print("Please run scripts/setup_stockfish.py first.")
        return

    # Initialize Engine
    transport, engine = await chess.engine.popen_uci(str(STOCKFISH_EXE))

    results = {}
    
    # Load Games
    game_files = list(GAMES_DIR.glob("*.json"))
    print(f"Found {len(game_files)} player files.")
    
    try:
        for idx, game_file in enumerate(game_files):
            username = game_file.stem.split("_")[-1]
            print(f"[{idx+1}/{len(game_files)}] Analyzing {username}...")
            
            with open(game_file, "r") as f:
                games = json.load(f)
                
            # Limit to recent 3 games to save time for this prototype
            games = games[:3] 
            
            player_stats = {
                "crit_total": 0, "crit_correct": 0,
                "norm_total": 0, "norm_correct": 0
            }
            
            for game_data in games:
                pgn_text = game_data.get("pgn")
                if pgn_text:
                    stats = await analyze_game(engine, pgn_text, username)
                    if stats:
                        for k, v in stats.items():
                            if k == "critical_total": player_stats["crit_total"] += v
                            elif k == "critical_correct": player_stats["crit_correct"] += v
                            elif k == "normal_total": player_stats["norm_total"] += v
                            elif k == "normal_correct": player_stats["norm_correct"] += v
                            
            # Calculate Index
            crit_acc = 0
            if player_stats["crit_total"] > 0:
                crit_acc = player_stats["crit_correct"] / player_stats["crit_total"]
                
            norm_acc = 0
            if player_stats["norm_total"] > 0:
                norm_acc = player_stats["norm_correct"] / player_stats["norm_total"]
                
            sniper_index = crit_acc - norm_acc
            
            print(f"  -> Critical Acc: {crit_acc*100:.1f}% ({player_stats['crit_correct']}/{player_stats['crit_total']})")
            print(f"  -> Normal Acc:   {norm_acc*100:.1f}% ({player_stats['norm_correct']}/{player_stats['norm_total']})")
            print(f"  -> Sniper Index: {sniper_index:.3f}")
            
            results[username] = {
                "sniper_index": round(sniper_index, 3),
                "critical_accuracy": round(crit_acc, 3),
                "normal_accuracy": round(norm_acc, 3),
                "critical_moves_count": player_stats["crit_total"],
                "games_analyzed": len(games)
            }
            
    finally:
        await engine.quit()
        
    # Save Results
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved sniper analysis to {RESULTS_FILE}")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(processing_loop())
