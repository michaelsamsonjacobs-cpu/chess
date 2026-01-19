"""Model abstractions used by ChessGuard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ModelResult:
    """Represents the outcome of a detection model inference."""

    score: float
    factors: List[str]


class DetectionModel:
    """Interface implemented by detection models."""

    def predict(self, features: Dict[str, float]) -> ModelResult:  # pragma: no cover - interface
        raise NotImplementedError
