"""Evaluation metrics for ChessGuard tournament replays."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .historical_replay import ReplayResult


@dataclass(frozen=True)
class EvaluationMetrics:
    precision: float
    recall: float
    true_positives: int
    false_positives: int
    false_negatives: int
    threshold: float


def compute_precision_recall(
    results: Iterable[ReplayResult], threshold: float
) -> EvaluationMetrics:
    tp = 0
    fp = 0
    fn = 0
    for result in results:
        is_positive_prediction = result.probability >= threshold
        if is_positive_prediction and result.label:
            tp += 1
        elif is_positive_prediction and not result.label:
            fp += 1
        elif not is_positive_prediction and result.label:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return EvaluationMetrics(
        precision=precision,
        recall=recall,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        threshold=threshold,
    )


__all__ = ["EvaluationMetrics", "compute_precision_recall"]
