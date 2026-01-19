"""Light-weight inference utilities used by the ChessGuard engine."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .preprocessing import PreprocessedGame


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


@dataclass(frozen=True)
class ModelExplanation:
    probability: float
    contributions: dict[str, float]


class ThreatModel:
    """Deterministic linear model with logistic calibration."""

    def __init__(self, weights: Mapping[str, float], bias: float = 0.0) -> None:
        self._weights: dict[str, float] = dict(weights)
        self._bias = float(bias)

    def _resolve_features(
        self, features: PreprocessedGame | Mapping[str, float]
    ) -> dict[str, float]:
        if isinstance(features, PreprocessedGame):
            return dict(features.feature_vector())
        return dict(features)

    def score(self, features: PreprocessedGame | Mapping[str, float]) -> float:
        vector = self._resolve_features(features)
        score = self._bias
        for name, value in vector.items():
            score += self._weights.get(name, 0.0) * value
        return score

    def predict_proba(self, features: PreprocessedGame | Mapping[str, float]) -> float:
        score = self.score(features)
        return _sigmoid(score)

    def predict_alert(
        self, features: PreprocessedGame | Mapping[str, float], threshold: float
    ) -> bool:
        probability = self.predict_proba(features)
        return probability >= threshold

    def explain(self, features: PreprocessedGame | Mapping[str, float]) -> ModelExplanation:
        vector = self._resolve_features(features)
        probability = self.predict_proba(vector)
        contributions: dict[str, float] = {}
        for name, value in vector.items():
            contributions[name] = self._weights.get(name, 0.0) * value
        contributions["bias"] = self._bias
        return ModelExplanation(probability=probability, contributions=contributions)

    @property
    def weights(self) -> Mapping[str, float]:
        return dict(self._weights)

    @property
    def bias(self) -> float:
        return self._bias


_DEFAULT_WEIGHTS = {
    "move_count": -0.03,
    "capture_balance": 0.4,
    "aggression_factor": 0.9,
    "unique_move_ratio": -0.2,
}
_DEFAULT_BIAS = 0.2


def load_default_model() -> ThreatModel:
    return ThreatModel(weights=_DEFAULT_WEIGHTS, bias=_DEFAULT_BIAS)


__all__ = [
    "ModelExplanation",
    "ThreatModel",
    "load_default_model",
]
