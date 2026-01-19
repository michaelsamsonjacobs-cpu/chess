"""Core engine module: structured-logging decision engine + heuristic/ML analysis engine.

This merges:
- Feature branch: ChessGuardEngine with structlog + Prometheus metrics operating over
  preprocessed games and a ThreatModel.
- Main branch: Engine that scores raw move sequences using python-chess with optional
  ML backends (Torch/LightGBM/scikit) and configurable thresholds.
"""

from __future__ import annotations

# ------------------------------- Common imports ------------------------------
import logging
import math
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

# ------------------------- Feature-branch dependencies -----------------------
from ._compat import Counter, Gauge, Histogram, Summary, get_logger

from .model import ModelExplanation, ThreatModel
from .preprocessing import PreprocessedGame

# --------------------------- Main-branch dependencies ------------------------
import chess
from .config import EngineConfig

try:  # Optional heavy dependencies; used only if available.
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore

try:  # Optional gradient-boosted backend
    import lightgbm  # type: ignore
except Exception:  # pragma: no cover
    lightgbm = None  # type: ignore

try:  # Optional classical ML loader
    import joblib  # type: ignore
except Exception:  # pragma: no cover
    joblib = None  # type: ignore


# =============================================================================
#                         Feature-branch Decision Engine
# =============================================================================

_logger = get_logger(__name__, component="engine")

_ENGINE_EVALUATIONS = Counter(
    "chessguard_engine_evaluations_total",
    "Total number of games evaluated by the engine.",
)
_ENGINE_ALERTS = Counter(
    "chessguard_engine_alerts_total",
    "Total number of games flagged for review.",
)
_ENGINE_LATENCY = Summary(
    "chessguard_engine_latency_seconds",
    "Wall clock time spent evaluating a single game.",
)
_ENGINE_PROBABILITY = Histogram(
    "chessguard_engine_probability",
    "Distribution of emitted cheating probabilities.",
    buckets=(0.2, 0.4, 0.6, 0.75, 0.9, 1.0),
)
_ENGINE_THRESHOLD = Gauge(
    "chessguard_engine_alert_threshold",
    "Current alert probability threshold configured for the engine.",
)


@dataclass(frozen=True)
class EngineResult:
    probability: float
    alert: bool
    evaluation_time: float
    contributions: dict[str, float]


class ChessGuardEngine:
    """Thresholding wrapper around a ThreatModel with metrics + structured logs."""

    def __init__(self, model: ThreatModel, alert_threshold: float = 0.75) -> None:
        self._model = model
        self._alert_threshold = float(alert_threshold)
        _ENGINE_THRESHOLD.set(self._alert_threshold)
        self._logger = _logger.bind(alert_threshold=self._alert_threshold)

    @property
    def alert_threshold(self) -> float:
        return self._alert_threshold

    @alert_threshold.setter
    def alert_threshold(self, value: float) -> None:
        self._alert_threshold = float(value)
        _ENGINE_THRESHOLD.set(self._alert_threshold)
        self._logger.info("threshold_updated", alert_threshold=self._alert_threshold)

    def evaluate(self, game: PreprocessedGame) -> EngineResult:
        start = time.perf_counter()
        explanation: ModelExplanation = self._model.explain(game)
        probability = explanation.probability
        alert = probability >= self._alert_threshold
        elapsed = time.perf_counter() - start

        _ENGINE_EVALUATIONS.inc()
        _ENGINE_LATENCY.observe(elapsed)
        _ENGINE_PROBABILITY.observe(probability)
        if alert:
            _ENGINE_ALERTS.inc()

        self._logger.info(
            "evaluation_completed",
            probability=probability,
            alert=alert,
            move_count=game.move_count,
            capture_balance=game.capture_balance,
        )

        return EngineResult(
            probability=probability,
            alert=alert,
            evaluation_time=elapsed,
            contributions=explanation.contributions,
        )

    def evaluate_many(self, games: Sequence[PreprocessedGame]) -> list[EngineResult]:
        return [self.evaluate(g) for g in games]

    def warm_up(self, games: Iterable[PreprocessedGame]) -> None:
        for game in games:
            self.evaluate(game)


# =============================================================================
#                            Main-branch Analysis Engine
# =============================================================================

MoveInput = Union[chess.Move, str]
"""Type alias accepted by the engine when describing moves."""

PIECE_VALUES = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.2,
    chess.BISHOP: 3.3,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
}
"""Rough material values used by the heuristic fallback model."""


class Engine:
    """Score move sequences and estimate the likelihood of assistance."""

    def __init__(self, config: Optional[EngineConfig] = None, logger: Optional[logging.Logger] = None) -> None:
        self.config = config or EngineConfig()
        self.logger = logger or logging.getLogger(__name__)
        self._models: Dict[str, Any] = {}
        self._load_models()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def score_moves(
        self,
        moves: Sequence[MoveInput],
        board: Optional[chess.Board] = None,
    ) -> List[Dict[str, Any]]:
        """Return per-move scores for the provided move sequence."""
        working_board = (board.copy(stack=False) if board is not None else chess.Board())
        scored_moves: List[Dict[str, Any]] = []

        for ply, move_input in enumerate(moves, start=1):
            move = self._parse_move(move_input, working_board)
            san = working_board.san(move)
            player = "white" if working_board.turn == chess.WHITE else "black"
            features = self._extract_features(working_board, move)
            score = self._evaluate_features(features)
            scored_moves.append(
                {
                    "ply": ply,
                    "move_number": (ply + 1) // 2,
                    "player": player,
                    "uci": move.uci(),
                    "san": san,
                    "score": score,
                    "features": list(features),
                }
            )
            working_board.push(move)

        return scored_moves

    def analyze(
        self,
        moves: Sequence[MoveInput],
        board: Optional[chess.Board] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the full scoring pipeline and compute cheat-likelihood metrics."""
        scored_moves = self.score_moves(moves, board)
        raw_scores = [entry["score"] for entry in scored_moves]
        smoothed = self._smooth_scores(raw_scores)
        thresholds = self.config.thresholds

        suspicious_count = 0
        for entry, smoothed_score in zip(scored_moves, smoothed):
            entry["smoothed_score"] = smoothed_score
            entry["is_suspicious"] = smoothed_score >= thresholds.suspicious_move
            if entry["is_suspicious"]:
                suspicious_count += 1

        suspicious_ratio = (suspicious_count / len(scored_moves)) if scored_moves else 0.0
        aggregate_score = self._aggregate_scores(smoothed)
        cheat_likelihood = self._compose_cheat_likelihood(aggregate_score, suspicious_ratio)
        meets_minimum = len(scored_moves) >= thresholds.minimum_moves
        flagged = (
            meets_minimum
            and cheat_likelihood >= thresholds.cheat_likelihood
            and suspicious_ratio >= thresholds.suspicious_ratio
        )

        response: Dict[str, Any] = {
            "cheat_likelihood": cheat_likelihood,
            "suspect": bool(flagged),
            "aggregate_score": aggregate_score,
            "suspicious_ratio": suspicious_ratio,
            "minimum_sample_size_met": meets_minimum,
            "moves": scored_moves,
        }

        combined_metadata: Dict[str, Any] = {}
        if self.config.metadata:
            combined_metadata.update(self.config.metadata)
        if metadata:
            combined_metadata.update(metadata)
        if combined_metadata:
            response["metadata"] = combined_metadata

        return response

    # ------------------------------------------------------------------
    # Model loading helpers
    # ------------------------------------------------------------------
    def _load_models(self) -> None:
        """Attempt to load configured models from disk."""
        model_path = Path(self.config.model.evaluation_model_path)
        if model_path.exists():
            loader = self._load_evaluation_backend(model_path)
            if loader is not None:
                self._models["evaluation"] = loader
        else:
            self.logger.info("Evaluation model not found at %s; using heuristic fallback.", model_path)

        aggregate_path = self.config.model.aggregate_model_path
        if aggregate_path:
            aggregate_path = Path(aggregate_path)
            if aggregate_path.exists():
                try:
                    if joblib is not None:
                        self._models["aggregate"] = joblib.load(aggregate_path)
                        self.logger.info("Loaded aggregate model from %s", aggregate_path)
                    else:  # pragma: no cover
                        self.logger.warning("joblib not available; unable to load %s", aggregate_path)
                except Exception as exc:  # pragma: no cover
                    self.logger.warning("Failed to load aggregate model %s: %s", aggregate_path, exc)
            else:
                self.logger.debug("Aggregate model path %s does not exist", aggregate_path)

    def _load_evaluation_backend(self, model_path: Path) -> Optional[Any]:
        """Load the evaluation model for the appropriate backend."""
        suffix = model_path.suffix.lower()
        try:
            if suffix in {".pt", ".pth"} and torch is not None:  # pragma: no cover
                model = torch.jit.load(str(model_path))
                model.eval()
                self.logger.info("Loaded TorchScript model from %s", model_path)
                return model
            if suffix in {".bin", ".joblib"} and joblib is not None:
                model = joblib.load(model_path)
                self.logger.info("Loaded joblib model from %s", model_path)
                return model
            if suffix in {".txt", ".lgb"} and lightgbm is not None:  # pragma: no cover
                booster = lightgbm.Booster(model_file=str(model_path))
                self.logger.info("Loaded LightGBM model from %s", model_path)
                return booster
        except Exception as exc:  # pragma: no cover
            self.logger.warning("Failed to load evaluation model %s: %s", model_path, exc)

        self.logger.debug("No compatible loader found for %s; falling back to heuristics.", model_path)
        return None

    # ------------------------------------------------------------------
    # Feature extraction and evaluation
    # ------------------------------------------------------------------
    def _parse_move(self, move: MoveInput, board: chess.Board) -> chess.Move:
        """Validate a SAN/UCI move against the current board."""
        if isinstance(move, chess.Move):
            if move not in board.legal_moves:
                raise ValueError(f"Illegal move {move} for board {board.fen()}")
            return move

        if isinstance(move, str):
            text = move.strip()
            if not text:
                raise ValueError("Empty move string encountered")
            try:
                parsed = board.parse_san(text)
            except ValueError:
                parsed = chess.Move.from_uci(text)
                if parsed not in board.legal_moves:
                    raise ValueError(f"Illegal move {move} for board {board.fen()}")
            return parsed

        raise TypeError(f"Unsupported move representation: {type(move)!r}")

    def _extract_features(self, board: chess.Board, move: chess.Move) -> Tuple[float, ...]:
        """Compute the feature vector consumed by the underlying model."""
        san = board.san(move)
        color_multiplier = 1.0 if board.turn == chess.WHITE else -1.0
        before_eval = color_multiplier * self._material_score(board)
        mobility_before = float(self._count_legal_moves(board))
        is_capture = board.is_capture(move)
        gives_check = board.gives_check(move)

        board.push(move)
        after_eval = -color_multiplier * self._material_score(board)
        mobility_after = float(self._count_legal_moves(board))
        board.pop()

        material_improvement = after_eval - before_eval
        mobility_delta = mobility_after - mobility_before
        expected_mobility = max(self.config.model.expected_mobility, 1.0)

        features = (
            math.tanh(material_improvement),
            1.0 if is_capture else 0.0,
            1.0 if gives_check else 0.0,
            math.tanh((mobility_after - expected_mobility) / expected_mobility),
            min(len(san) / 6.0, 2.0),
        )
        return features

    def _evaluate_features(self, features: Sequence[float]) -> float:
        """Run the model (or fallback heuristic) on a feature vector."""
        model = self._models.get("evaluation")
        if model is None:
            return self._fallback_score(features)

        # Torch nn.Module
        if torch is not None and hasattr(torch, "nn") and isinstance(getattr(model, "__class__", None), type) and hasattr(model, "forward"):  # pragma: no cover
            with torch.no_grad():
                tensor = torch.tensor([features], dtype=getattr(torch, self.config.model.dtype, torch.float32))
                output = model(tensor.to(self.config.model.device))
                value = output.squeeze().detach().cpu().item()
            return float(self._sigmoid(value))

        # TorchScript callable
        if callable(model) and torch is not None and hasattr(model, "__call__"):  # pragma: no cover
            try:
                with torch.no_grad():
                    tensor = torch.tensor([features], dtype=getattr(torch, self.config.model.dtype, torch.float32))
                    value = model(tensor.to(self.config.model.device))
                    if hasattr(value, "item"):
                        value = value.item()
                    elif isinstance(value, (list, tuple)):
                        value = value[-1]
                return float(self._sigmoid(float(value)))
            except Exception:
                pass

        # LightGBM Booster
        if lightgbm is not None and isinstance(model, lightgbm.Booster):  # pragma: no cover
            value = model.predict([features])[0]
            return float(value)

        # scikit-learn style estimators
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba([features])[0]
            if isinstance(proba, (list, tuple)):
                return float(proba[-1])
            try:
                return float(proba)
            except TypeError:
                return self._fallback_score(features)

        if callable(model):
            value = model(features)
            if isinstance(value, (list, tuple)):
                value = value[-1]
            try:
                return float(value)
            except (TypeError, ValueError):
                return self._fallback_score(features)

        return self._fallback_score(features)

    def _fallback_score(self, features: Sequence[float]) -> float:
        """Simple logistic model used when no learned model is available."""
        bias = self.config.model.fallback_bias
        total = bias
        for weight, value in zip(self.config.model.fallback_weights, features):
            total += weight * value
        return self._sigmoid(total)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _smooth_scores(self, scores: Sequence[float]) -> List[float]:
        window = max(int(self.config.smoothing_window), 1)
        if window <= 1:
            return list(scores)

        smoothed: List[float] = []
        accumulator: List[float] = []
        for score in scores:
            accumulator.append(score)
            if len(accumulator) > window:
                accumulator.pop(0)
            smoothed.append(sum(accumulator) / len(accumulator))
        return smoothed

    def _aggregate_scores(self, scores: Sequence[float]) -> float:
        if not scores:
            return 0.0

        strategy = (self.config.aggregator or "mean").lower()
        if strategy == "median":
            return float(median(scores))
        if strategy == "max":
            return float(max(scores))
        return float(mean(scores))

    def _compose_cheat_likelihood(self, aggregate: float, suspicious_ratio: float) -> float:
        weights = dict(self.config.cheat_score_weights)
        aggregate_weight = float(weights.get("aggregate", 0.5))
        ratio_weight = float(weights.get("suspicious_ratio", 0.5))
        total_weight = aggregate_weight + ratio_weight
        if total_weight <= 0:
            return max(0.0, min(1.0, aggregate))
        raw = aggregate * aggregate_weight + suspicious_ratio * ratio_weight
        score = raw / total_weight
        return max(0.0, min(1.0, score))

    def _material_score(self, board: chess.Board) -> float:
        score = 0.0
        for piece_type, value in PIECE_VALUES.items():
            score += value * len(board.pieces(piece_type, chess.WHITE))
            score -= value * len(board.pieces(piece_type, chess.BLACK))
        return score

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    @staticmethod
    def _count_legal_moves(board: chess.Board) -> int:
        return sum(1 for _ in board.legal_moves)


__all__ = ["ChessGuardEngine", "EngineResult", "Engine", "MoveInput"]
