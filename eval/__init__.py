"""Evaluation harnesses for ChessGuard."""

from .calibration import calibration_curve, save_calibration_plot
from .historical_replay import (
    HistoricalGame,
    ReplayResult,
    load_historical_dataset,
    replay_tournament,
)
from .metrics import EvaluationMetrics, compute_precision_recall

__all__ = [
    "HistoricalGame",
    "ReplayResult",
    "load_historical_dataset",
    "replay_tournament",
    "EvaluationMetrics",
    "compute_precision_recall",
    "calibration_curve",
    "save_calibration_plot",
]
