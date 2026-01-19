"""Service layer orchestrating preprocessing, inference, and response building."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ._compat import Counter, Gauge, Summary, generate_latest, get_logger
from .engine import ChessGuardEngine, EngineResult
from .preprocessing import RawGame, preprocess_games

_SERVICE_LOGGER = get_logger(__name__, component="service")

_REQUEST_COUNTER = Counter(
    "chessguard_service_requests_total",
    "Total API calls received by the ChessGuard service.",
    labelnames=("endpoint",),
)
_REQUEST_LATENCY = Summary(
    "chessguard_service_latency_seconds",
    "Latency of service endpoints.",
    labelnames=("endpoint",),
)
_INFLIGHT = Gauge(
    "chessguard_service_inflight_requests",
    "Concurrent in-flight service requests.",
    labelnames=("endpoint",),
)


@dataclass(frozen=True)
class TournamentGameInput:
    game_id: str
    moves: Sequence[str]
    result: str


@dataclass(frozen=True)
class TournamentEvaluationRequest:
    tournament_id: str
    games: Sequence[TournamentGameInput]


@dataclass(frozen=True)
class TournamentGameEvaluation:
    game_id: str
    probability: float
    alert: bool


@dataclass(frozen=True)
class TournamentEvaluationResponse:
    tournament_id: str
    evaluations: Sequence[TournamentGameEvaluation]
    alert_rate: float
    summary: dict[str, float]


class ChessGuardService:
    def __init__(self, engine: ChessGuardEngine) -> None:
        self._engine = engine
        self._logger = _SERVICE_LOGGER

    def evaluate_tournament(
        self, request: TournamentEvaluationRequest
    ) -> TournamentEvaluationResponse:
        endpoint = "evaluate_tournament"
        _REQUEST_COUNTER.labels(endpoint=endpoint).inc()
        _INFLIGHT.labels(endpoint=endpoint).inc()
        try:
            with _REQUEST_LATENCY.labels(endpoint=endpoint).time():
                raw_games: list[RawGame] = [
                    RawGame(moves=game.moves, result=game.result) for game in request.games
                ]
                preprocessed = preprocess_games(raw_games)
                engine_results = self._engine.evaluate_many(preprocessed)
                evaluations = self._build_evaluations(request.games, engine_results)
                alert_rate = self._compute_alert_rate(evaluations)
                summary = {
                    "games_evaluated": float(len(evaluations)),
                    "alerts": float(sum(1 for evaluation in evaluations if evaluation.alert)),
                    "threshold": self._engine.alert_threshold,
                }
                self._logger.info(
                    "tournament_evaluated",
                    tournament_id=request.tournament_id,
                    games=len(evaluations),
                    alerts=summary["alerts"],
                    alert_rate=alert_rate,
                )
                return TournamentEvaluationResponse(
                    tournament_id=request.tournament_id,
                    evaluations=evaluations,
                    alert_rate=alert_rate,
                    summary=summary,
                )
        finally:
            _INFLIGHT.labels(endpoint=endpoint).dec()

    @staticmethod
    def _build_evaluations(
        games: Sequence[TournamentGameInput], results: Sequence[EngineResult]
    ) -> list[TournamentGameEvaluation]:
        evaluations: list[TournamentGameEvaluation] = []
        for game, result in zip(games, results, strict=True):
            evaluations.append(
                TournamentGameEvaluation(
                    game_id=game.game_id,
                    probability=result.probability,
                    alert=result.alert,
                )
            )
        return evaluations

    @staticmethod
    def _compute_alert_rate(evaluations: Sequence[TournamentGameEvaluation]) -> float:
        if not evaluations:
            return 0.0
        alerts = sum(1 for evaluation in evaluations if evaluation.alert)
        return alerts / len(evaluations)

    @staticmethod
    def export_metrics() -> bytes:
        return generate_latest()


__all__ = [
    "ChessGuardService",
    "TournamentEvaluationRequest",
    "TournamentEvaluationResponse",
    "TournamentGameInput",
    "TournamentGameEvaluation",
]
