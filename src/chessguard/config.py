"""Configuration objects used by the ChessGuard engine and pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Optional, Tuple


@dataclass
class ModelConfig:
    """Runtime options for loading and executing evaluation models.

    The paths are intentionally kept generic so that different backends
    (PyTorch, LightGBM, ONNX, etc.) can be plugged in without modifying the
    core engine logic.  When a referenced file does not exist the engine falls
    back to an analytical heuristic model.
    """

    evaluation_model_path: Path = Path("models/move_quality.onnx")
    """Primary model that scores the quality of individual moves."""

    aggregate_model_path: Optional[Path] = None
    """Optional secondary model used to combine move scores into a session score."""

    device: str = "cpu"
    """Preferred device string for deep learning frameworks (e.g. ``"cpu"`` or ``"cuda"``)."""

    dtype: str = "float32"
    """Data type hint used when instantiating tensor-based models."""

    fallback_bias: float = -0.15
    """Bias term used by the analytical fallback model when no binary file is present."""

    fallback_weights: Tuple[float, ...] = (1.25, 0.9, 0.55, 0.35, 0.2)
    """Weights for the heuristic fallback model; see :meth:`Engine._fallback_score`."""

    expected_mobility: float = 30.0
    """Average legal move count expected for balanced middlegame positions."""

    def resolved_evaluation_path(self, base_dir: Optional[Path] = None) -> Path:
        """Return an absolute path to the evaluation model.

        Parameters
        ----------
        base_dir:
            Optional directory that overrides the default relative lookup.
        """

        if base_dir is not None:
            return Path(base_dir) / self.evaluation_model_path
        return self.evaluation_model_path


@dataclass
class ThresholdConfig:
    """Thresholds used to interpret model scores."""

    cheat_likelihood: float = 0.75
    """Minimum aggregated score that triggers a cheating alert."""

    suspicious_move: float = 0.82
    """Per-move score above which an individual move is marked as suspicious."""

    minimum_moves: int = 20
    """Number of moves required before a verdict is considered reliable."""

    suspicious_ratio: float = 0.55
    """Minimum fraction of suspicious moves required for a conclusive flag."""


@dataclass
class EngineConfig:
    """Configuration for :class:`~chessguard.engine.Engine` execution."""

    model: ModelConfig = field(default_factory=ModelConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    smoothing_window: int = 5
    """Window size (in plies) used for moving-average smoothing."""

    aggregator: str = "mean"
    """Aggregation strategy for rolling up per-move scores (``mean``/``median``/``max``)."""

    cheat_score_weights: Mapping[str, float] = field(
        default_factory=lambda: {"aggregate": 0.6, "suspicious_ratio": 0.4}
    )
    """Linear weights applied when computing the final cheat likelihood metric."""

    metadata: MutableMapping[str, str] = field(default_factory=dict)
    """Arbitrary metadata injected into every engine response."""


@dataclass
class PipelineConfig:
    """High-level options for the end-to-end analysis pipeline."""

    engine: EngineConfig = field(default_factory=EngineConfig)
    chunk_size: int = 32
    """Number of plies processed per batch during inference."""

    inference_batch_size: int = 128
    """Soft limit for the number of feature vectors sent to the model at once."""

    allow_incomplete_games: bool = False
    """Whether to analyse games that ended abruptly (e.g., resignation, abort)."""

    postprocess: bool = True
    """Toggle for optional post-processing and report shaping."""

    extra_metadata: Dict[str, str] = field(default_factory=dict)
    """Additional metadata forwarded to downstream consumers."""


DEFAULT_ENGINE_CONFIG = EngineConfig()
"""Default configuration used when callers do not supply their own engine config."""

DEFAULT_PIPELINE_CONFIG = PipelineConfig()
"""Default pipeline configuration for convenience constructors."""

__all__ = [
    "DEFAULT_ENGINE_CONFIG",
    "DEFAULT_PIPELINE_CONFIG",
    "EngineConfig",
    "ModelConfig",
    "PipelineConfig",
    "ThresholdConfig",
]
