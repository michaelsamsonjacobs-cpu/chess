"""Hybrid statistical model using logistic regression."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

from .base import DetectionModel, ModelResult

FeatureSample = Tuple[Dict[str, float], float]


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


class HybridLogisticModel(DetectionModel):
    """Lightweight logistic regression model with explainability hooks."""

    def __init__(self, weights: Dict[str, float] | None = None, bias: float = -1.0) -> None:
        self.weights = weights or {
            "check_rate": 1.8,
            "capture_rate": 1.4,
            "novelty_ply": 0.05,
            "avg_time": -0.08,
            "std_time": -0.15,
            "burstiness": -0.25,
            "annotation_rate": -0.9,
            "tempo_shift_score": 0.25,
            "pace_balance": -0.1,
        }
        self.bias = bias

    def predict(self, features: Dict[str, float]) -> ModelResult:
        total = self.bias
        contributions: List[Tuple[str, float]] = []
        for name, weight in self.weights.items():
            contribution = weight * float(features.get(name, 0.0))
            contributions.append((name, contribution))
            total += contribution
        score = _sigmoid(total)
        positive = sorted([item for item in contributions if item[1] > 0], key=lambda item: item[1], reverse=True)
        negative = sorted([item for item in contributions if item[1] < 0], key=lambda item: item[1])
        factors: List[str] = []
        for name, value in positive[:3]:
            factors.append(f"{name} contributes +{value:.2f}")
        for name, value in negative[:2]:
            factors.append(f"{name} contributes {value:.2f}")
        if not factors:
            factors.append("No significant feature contributions")
        return ModelResult(score=score, factors=factors)

    def train(self, samples: Iterable[FeatureSample], epochs: int = 200, learning_rate: float = 0.01) -> None:
        dataset = list(samples)
        if not dataset:
            return
        feature_names = set(self.weights.keys())
        for features, _ in dataset:
            feature_names.update(features.keys())
        for name in feature_names:
            self.weights.setdefault(name, 0.0)
        n = len(dataset)
        for _ in range(epochs):
            grad_bias = 0.0
            grad_weights = {name: 0.0 for name in self.weights}
            for features, label in dataset:
                linear = self.bias
                for name, weight in self.weights.items():
                    linear += weight * float(features.get(name, 0.0))
                prediction = _sigmoid(linear)
                error = prediction - label
                grad_bias += error
                for name in self.weights:
                    grad_weights[name] += error * float(features.get(name, 0.0))
            self.bias -= learning_rate * (grad_bias / n)
            for name in self.weights:
                self.weights[name] -= learning_rate * (grad_weights[name] / n)
