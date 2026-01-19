"""Unit tests for the preprocessing utilities."""

from __future__ import annotations

import pytest

from chessguard.preprocessing import PreprocessedGame, RawGame, preprocess_game


def test_preprocess_game_normalizes_moves_and_features() -> None:
    raw = RawGame(
        moves=["1. e4", "... e5", "Nf3+", "Nc6", "Bxb5+"],
        result="1-0",
    )
    preprocessed = preprocess_game(raw)

    assert preprocessed.normalized_moves == ("e4", "e5", "nf3", "nc6", "bxb5")
    assert preprocessed.move_count == 5
    assert preprocessed.capture_balance == pytest.approx(1.0)
    assert preprocessed.aggression_factor == pytest.approx(1 / 5)
    assert preprocessed.unique_move_ratio == pytest.approx(1.0)

    feature_vector = preprocessed.feature_vector()
    assert set(feature_vector.keys()) == {
        "move_count",
        "capture_balance",
        "aggression_factor",
        "unique_move_ratio",
    }
    assert feature_vector["move_count"] == pytest.approx(5.0)


def test_preprocessed_game_feature_vector_matches_dataclass() -> None:
    game = PreprocessedGame(
        normalized_moves=("e4", "e5"),
        move_count=2,
        capture_balance=0.5,
        aggression_factor=0.5,
        unique_move_ratio=1.0,
        result="1-0",
    )
    features = game.feature_vector()
    assert features["move_count"] == pytest.approx(2.0)
    assert features["capture_balance"] == pytest.approx(0.5)
    assert features["aggression_factor"] == pytest.approx(0.5)
    assert features["unique_move_ratio"] == pytest.approx(1.0)
