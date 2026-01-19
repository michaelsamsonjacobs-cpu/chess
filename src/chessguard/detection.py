"""Suspicion scoring utilities.

The heuristics here translate aggregated metrics into a scalar score that can be
triaged by moderators. They blend centipawn-loss thresholds, engine agreement
streaks, and time-pressure anomalies as popularised by the open-source projects
surveyed in ``docs/research/cheating_repos.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from . import analysis

DEFAULT_THRESHOLDS = {
    "acpl_suspicious": 25.0,
    "acpl_min": 5.0,
    "engine_agreement": 0.75,
    "fast_engine_agreement": 0.65,
    "engine_streak": 8,
}

DEFAULT_WEIGHTS = {
    "acpl": 0.35,
    "engine_agreement": 0.3,
    "fast_engine_agreement": 0.2,
    "engine_streak": 0.15,
}


@dataclass
class SuspicionBreakdown:
    """Structured representation of the suspicion score."""

    score: float
    components: Dict[str, float]
    thresholds: Mapping[str, float]


def _score_lower_is_better(value: float, *, threshold: float, minimum: float) -> float:
    if value >= threshold:
        return 0.0
    if value <= minimum:
        return 1.0
    return (threshold - value) / (threshold - minimum)


def _score_higher_is_better(value: Optional[float], *, threshold: float) -> float:
    if value is None:
        return 0.0
    if value <= threshold:
        return 0.0
    return min((value - threshold) / (1.0 - threshold), 1.0)


def _score_streak(value: int, *, threshold: int) -> float:
    if value <= threshold:
        return 0.0
    return min((value - threshold) / max(threshold, 1), 1.0)


def suspicion_components(
    summary: analysis.GameSummary,
    *,
    thresholds: Mapping[str, float] = DEFAULT_THRESHOLDS,
) -> Dict[str, float]:
    """Convert a :class:`GameSummary` into weighted suspicion components."""

    components = {
        "acpl": _score_lower_is_better(
            summary.average_centipawn_loss,
            threshold=thresholds["acpl_suspicious"],
            minimum=thresholds["acpl_min"],
        ),
        "engine_agreement": _score_higher_is_better(
            summary.engine_agreement_rate, threshold=thresholds["engine_agreement"]
        ),
        "engine_streak": _score_streak(
            summary.max_engine_streak, threshold=int(thresholds["engine_streak"])
        ),
    }

    if summary.fast_engine_agreement_rate is not None:
        components["fast_engine_agreement"] = _score_higher_is_better(
            summary.fast_engine_agreement_rate,
            threshold=thresholds["fast_engine_agreement"],
        )
    else:
        components["fast_engine_agreement"] = 0.0

    return components


def suspicion_score(
    summary: analysis.GameSummary,
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    thresholds: Mapping[str, float] = DEFAULT_THRESHOLDS,
) -> float:
    """Compute a weighted suspicion score in the range [0, 1]."""

    components = suspicion_components(summary, thresholds=thresholds)
    total_weight = sum(weights.get(name, 0.0) for name in components)
    if total_weight == 0:
        return 0.0

    score = 0.0
    for name, value in components.items():
        weight = weights.get(name, 0.0)
        score += weight * value
    return score / total_weight


def explain_suspicion(
    summary: analysis.GameSummary,
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    thresholds: Mapping[str, float] = DEFAULT_THRESHOLDS,
) -> SuspicionBreakdown:
    """Return the suspicion score alongside its component contributions."""

    components = suspicion_components(summary, thresholds=thresholds)
    score = suspicion_score(summary, weights=weights, thresholds=thresholds)
    weighted_components = {
        name: components[name] * weights.get(name, 0.0)
        for name in components
    }
    return SuspicionBreakdown(
        score=score,
        components=weighted_components,
        thresholds=thresholds,
    )
