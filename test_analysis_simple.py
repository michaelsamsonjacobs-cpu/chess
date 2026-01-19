
import os
import sys
sys.path.insert(0, os.getcwd())
import chess.engine
import pandas as pd
from src.chessguard.analysis import evaluate_game

PGN_TEXT = """[Event "Test Game"]
[Site "ChessGuard"]
[Date "2024.12.17"]
[Round "1"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O Nge7 8. Ng5 O-O 9. Qh5 h6 10. Nxf7 Rxf7 11. Bxf7+ Kf8 12. Bb3 Qe8 13. Qf3+ Nf5 14. Qxf5+ Ke7 15. Ba3+ Kd8 16. Bf7 Qe5 17. Qh7 d6 18. Qg8+ Ke7 19. f4 Qf6 20. Qe8# 1-0"""

ENGINE_PATH = os.environ.get("CHECK_ENGINE_PATH", "bin/stockfish-windows-x86-64-avx2.exe")

def main():
    print(f"Testing analysis with engine at: {ENGINE_PATH}")
    if not os.path.exists(ENGINE_PATH):
        print("ERROR: Engine not found!")
        return

    try:
        df = evaluate_game(PGN_TEXT, engine_path=ENGINE_PATH, depth=10)
        print("Analysis successful!")
        print(df[["ply", "best_score_cp", "centipawn_loss", "is_engine_move"]].head())
    except Exception as e:
        print(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
