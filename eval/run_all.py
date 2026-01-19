"""Command line entry point for running the evaluation harness."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from chessguard import ChessGuardEngine, load_default_model

from .calibration import calibration_curve, save_calibration_plot
from .historical_replay import load_historical_dataset, replay_tournament
from .metrics import compute_precision_recall


def run(dataset_path: Path, output_path: Path, threshold: float, bins: int) -> tuple[Path, Path]:
    games = load_historical_dataset(dataset_path)
    engine = ChessGuardEngine(load_default_model(), alert_threshold=threshold)
    results = replay_tournament(engine, games)
    metrics = compute_precision_recall(results, threshold=threshold)
    curve = calibration_curve(results, bins=bins)

    output_path.mkdir(parents=True, exist_ok=True)
    metrics_path = output_path / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(metrics), handle, indent=2)
    calibration_path = output_path / "calibration.png"
    save_calibration_plot(curve, calibration_path)
    summary_path = output_path / "summary.txt"
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "ChessGuard evaluation summary\n"
            f"Dataset: {dataset_path}\n"
            f"Games: {len(results)}\n"
            f"Threshold: {threshold:.2f}\n"
            f"Precision: {metrics.precision:.2f}\n"
            f"Recall: {metrics.recall:.2f}\n"
        )
    print(
        json.dumps(
            {
                "dataset": str(dataset_path),
                "threshold": threshold,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "metrics_path": str(metrics_path),
                "calibration_path": str(calibration_path),
            },
            indent=2,
        )
    )
    return metrics_path, calibration_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ChessGuard evaluation harnesses")
    default_dataset = Path(__file__).resolve().parent / "data" / "sample_tournament.json"
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_dataset,
        help="Path to a JSON dataset to replay.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory where evaluation artefacts will be written.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Alert threshold applied during evaluation.",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=5,
        help="Number of bins to use for the calibration plot.",
    )
    args = parser.parse_args()
    run(
        dataset_path=args.dataset,
        output_path=args.output,
        threshold=args.threshold,
        bins=args.bins,
    )


if __name__ == "__main__":
    main()
