"""Tests for the lightweight threat model."""

from __future__ import annotations

import pytest

from chessguard.model import load_default_model
from chessguard.preprocessing import PreprocessedGame, RawGame, preprocess_game


def test_model_probability_is_well_formed() -> None:
    model = load_default_model()
    raw = RawGame(
        moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6", "dxc6"],
        result="1-0",
    )
    game = preprocess_game(raw)
    probability = model.predict_proba(game)
    assert 0.0 < probability < 1.0


def test_model_respects_feature_directionality() -> None:
    model = load_default_model()
    low_risk = PreprocessedGame(
        normalized_moves=("e4", "e5"),
        move_count=2,
        capture_balance=0.0,
        aggression_factor=0.0,
        unique_move_ratio=1.0,
        result="1-0",
    )
    high_risk = PreprocessedGame(
        normalized_moves=("exd5", "cxd5"),
        move_count=2,
        capture_balance=3.0,
        aggression_factor=1.0,
        unique_move_ratio=0.5,
        result="1-0",
    )
    low_probability = model.predict_proba(low_risk)
    high_probability = model.predict_proba(high_risk)
    assert high_probability > low_probability

    explanation = model.explain(high_risk)
    assert explanation.probability == pytest.approx(high_probability)
    expected_score = model.score(high_risk)
    assert sum(explanation.contributions.values()) == pytest.approx(expected_score)
