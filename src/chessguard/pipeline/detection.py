"""High level detection pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from ..data.telemetry import SessionTelemetry
from ..features.extractor import build_feature_vector
from ..models import DetectionModel, HybridLogisticModel, ModelResult, RuleBasedModel
from ..utils.pgn import PGNGame


@dataclass
class DetectionReport:
    """Structured output describing the detection outcome for a game."""

    features: Dict[str, float]
    model_results: Dict[str, ModelResult]
    aggregate_score: float
    recommended_action: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "features": dict(self.features),
            "models": {name: {"score": result.score, "factors": list(result.factors)} for name, result in self.model_results.items()},
            "aggregate_score": self.aggregate_score,
            "recommended_action": self.recommended_action,
        }


class DetectionPipeline:
    """Coordinates feature extraction and model execution."""

    def __init__(self, models: Optional[List[DetectionModel]] = None) -> None:
        self.models = models or [RuleBasedModel(), HybridLogisticModel()]

    def run(self, game: PGNGame, telemetry: Optional[SessionTelemetry] = None) -> DetectionReport:
        feature_vector = build_feature_vector(game, telemetry)
        features = feature_vector.as_dict()
        results: Dict[str, ModelResult] = {}
        for model in self.models:
            result = model.predict(features)
            results[type(model).__name__] = result
        aggregate = sum(result.score for result in results.values()) / len(results) if results else 0.0
        action = self._recommend_action(aggregate)
        return DetectionReport(features=features, model_results=results, aggregate_score=aggregate, recommended_action=action)

    @staticmethod
    def _recommend_action(score: float) -> str:
        if score >= 0.75:
            return "Escalate to manual review and engine cross-check"
        if score >= 0.5:
            return "Monitor future games and request additional telemetry"
        if score >= 0.3:
            return "Low concern; continue passive monitoring"
        return "No immediate action"


def batch_run(games: Iterable[PGNGame], telemetry: Optional[SessionTelemetry] = None, pipeline: Optional[DetectionPipeline] = None) -> List[DetectionReport]:
    pipeline = pipeline or DetectionPipeline()
    return [pipeline.run(game, telemetry=telemetry) for game in games]
