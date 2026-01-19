import sys
import logging
from server.database import SessionLocal
from server.services.analysis import GameAnalysisPipeline

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG)

def test_ingest():
    db = SessionLocal()
    pipeline = GameAnalysisPipeline(db)
    
    # Mock PGN similar to Chess.com
    pgn_text = """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.01"]
[Round "-"]
[White "TestPlayerWhite"]
[Black "TestPlayerBlack"]
[Result "1-0"]
[WhiteElo "1200"]
[BlackElo "1200"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. c4 c6 12. cxb5 axb5 13. Nc3 Bb7 14. Bg5 b4 15. Nb1 h6 16. Bh4 c5 17. dxe5 Nxe4 18. Bxe7 Qxe7 19. exd6 Qf6 20. Nbd2 Nxd6 21. Nc4 Nxc4 22. Bxc4 Nb6 23. Ne5 Rae8 24. Bxf7+ Rxf7 25. Nxf7 Rxe1+ 26. Qxe1 Kxf7 27. Qe3 Qg5 28. Qxg5 hxg5 29. b3 Ke6 30. a3 bxa3 31. Rxa3 Kd6 32. Ra7 Kc6 33. Ra1 Bc8 34. Kf1 Be6 35. Rb1 Kb5 36. Ke2 Kb4 37. Ke3 Bxb3 38. Ke4 c4 39. Kf5 c3 40. Kxg5 c2 41. Rc1 Kc3 42. Kg6 Kd2 43. Rxc2+ Bxc2+ 44. Kxg7 Ke2 45. g4 Kxf2 46. h4 Kg3 47. h5 Kxg4 48. h6 Kg5 49. h7 Bxh7 50. Kxh7 1-0"""
    
    try:
        print("Attempting to ingest Chess.com-style PGN...")
        game, created = pipeline.ingest_game(
            lichess_id="chesscom_debug_1", # unique ID
            pgn_text=pgn_text,
            source="chesscom",
            force=True
        )
        db.commit()
        db.refresh(game)
        print(f"Ingestion successful! Game ID: {game.id}")
        
        print("Attempting to enqueue analysis...")
        from server.tasks import enqueue_game_analysis
        enqueue_game_analysis(game.id, force=True)
        print("Enqueue successful!")
        
    except Exception as e:
        print(f"CAUGHT EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_ingest()
