from pathlib import Path

from chessguard.data.loader import load_single_game, load_telemetry
from chessguard.features.extractor import build_feature_vector


ROOT = Path(__file__).resolve().parents[1]


def test_feature_vector_contains_expected_keys():
    game = load_single_game(ROOT / "examples" / "sample_game.pgn")
    telemetry = load_telemetry(ROOT / "examples" / "sample_telemetry.json")
    vector = build_feature_vector(game, telemetry)
    features = vector.as_dict()
    assert features["ply_count"] == 49.0
    assert 0.0 < features["capture_rate"] < 1.0
    assert "avg_time" in features and features["avg_time"] > 0
    assert "burstiness" in features
    assert abs(features["capture_balance"]) < 1
