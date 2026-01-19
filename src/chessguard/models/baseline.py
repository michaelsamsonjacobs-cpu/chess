"""Rule based cheat detection heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from .base import DetectionModel, ModelResult


Condition = Callable[[Dict[str, float]], bool]


@dataclass
class Rule:
    feature: str
    condition: Condition
    weight: float
    description: str


def _safe_get(features: Dict[str, float], key: str) -> float:
    return float(features.get(key, 0.0))


class RuleBasedModel(DetectionModel):
    """Simple interpretable rule based detector."""

    def __init__(self, base_score: float = 0.15) -> None:
        self.base_score = base_score
        self.rules: List[Rule] = [
            Rule(
                feature="avg_time",
                condition=lambda f: _safe_get(f, "avg_time") <= 4.0 and _safe_get(f, "std_time") <= 2.0,
                weight=0.25,
                description="Consistently fast move execution",
            ),
            Rule(
                feature="burstiness",
                condition=lambda f: _safe_get(f, "burstiness") < 0.35,
                weight=0.15,
                description="Low timing burstiness (engine like pacing)",
            ),
            Rule(
                feature="novelty_ply",
                condition=lambda f: _safe_get(f, "novelty_ply") >= 20,
                weight=0.1,
                description="Deep opening preparation",
            ),
            Rule(
                feature="check_rate",
                condition=lambda f: _safe_get(f, "check_rate") >= 0.35,
                weight=0.1,
                description="High proportion of checking moves",
            ),
            Rule(
                feature="annotation_rate",
                condition=lambda f: _safe_get(f, "annotation_rate") <= 0.02,
                weight=0.05,
                description="Unusually clean move annotations",
            ),
            Rule(
                feature="pace_balance",
                condition=lambda f: abs(_safe_get(f, "pace_balance")) <= 1.0,
                weight=0.05,
                description="Symmetric think times between players",
            ),
        ]
        self.mitigations: List[Rule] = [
            Rule(
                feature="long_pause_rate",
                condition=lambda f: _safe_get(f, "long_pause_rate") > 0.15,
                weight=-0.1,
                description="Contains natural long pauses",
            ),
            Rule(
                feature="short_burst_rate",
                condition=lambda f: _safe_get(f, "short_burst_rate") > 0.5,
                weight=-0.1,
                description="Contains frequent short bursts",
            ),
        ]

    def predict(self, features: Dict[str, float]) -> ModelResult:
        score = self.base_score
        factors: List[str] = []
        for rule in self.rules:
            if rule.condition(features):
                score += rule.weight
                factors.append(rule.description)
        for rule in self.mitigations:
            if rule.condition(features):
                score += rule.weight
                factors.append(rule.description)
        score = max(0.0, min(1.0, score))
        if not factors:
            factors.append("No rule triggers; baseline risk applied")
        return ModelResult(score=score, factors=factors)
