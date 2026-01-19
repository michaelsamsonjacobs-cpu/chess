"""Calibration utilities for ChessGuard evaluation harnesses."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .historical_replay import ReplayResult


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    mean_prediction: float
    positive_rate: float
    count: int


def calibration_curve(results: Iterable[ReplayResult], bins: int = 5) -> list[CalibrationBin]:
    if bins <= 0:
        raise ValueError("bins must be positive")
    bucket_width = 1.0 / bins
    counts = [0 for _ in range(bins)]
    probability_sums = [0.0 for _ in range(bins)]
    positive_counts = [0 for _ in range(bins)]
    for result in results:
        index = min(int(result.probability / bucket_width), bins - 1)
        counts[index] += 1
        probability_sums[index] += result.probability
        if result.label:
            positive_counts[index] += 1
    curve: list[CalibrationBin] = []
    for idx in range(bins):
        lower = idx * bucket_width
        upper = (idx + 1) * bucket_width
        if counts[idx] == 0:
            curve.append(CalibrationBin(lower, upper, 0.0, 0.0, 0))
            continue
        mean_prediction = probability_sums[idx] / counts[idx]
        positive_rate = positive_counts[idx] / counts[idx]
        curve.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                mean_prediction=mean_prediction,
                positive_rate=positive_rate,
                count=counts[idx],
            )
        )
    return curve


def save_calibration_plot(curve: Sequence[CalibrationBin], output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    mean_predictions = [bin.mean_prediction for bin in curve]
    positive_rates = [bin.positive_rate for bin in curve]
    ax.plot(mean_predictions, positive_rates, marker="o", label="Observed")
    ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", color="gray", label="Ideal")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed positive rate")
    ax.set_title("ChessGuard Calibration")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="best")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


__all__ = ["CalibrationBin", "calibration_curve", "save_calibration_plot"]
