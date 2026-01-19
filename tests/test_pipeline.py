from pathlib import Path

from chessguard.data.loader import load_single_game, load_telemetry
from chessguard.pipeline.detection import DetectionPipeline

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_generates_report():
    game = load_single_game(ROOT / "examples" / "sample_game.pgn")
    telemetry = load_telemetry(ROOT / "examples" / "sample_telemetry.json")
    pipeline = DetectionPipeline()
    report = pipeline.run(game, telemetry)
    assert 0.0 <= report.aggregate_score <= 1.0
    assert "RuleBasedModel" in report.model_results
    assert "HybridLogisticModel" in report.model_results
    assert isinstance(report.to_dict()["features"], dict)
