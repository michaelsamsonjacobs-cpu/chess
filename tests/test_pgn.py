from pathlib import Path

from chessguard.utils.pgn import parse_pgn


def test_parse_sample_game():
    root = Path(__file__).resolve().parents[1]
    text = (root / "examples" / "sample_game.pgn").read_text(encoding="utf8")
    game = parse_pgn(text)
    assert game.white_player == "Expert"
    assert game.black_player == "Challenger"
    assert len(game.moves) == 25
    assert game.moves[0].white == "e4"
    assert game.moves[-1].black is None
