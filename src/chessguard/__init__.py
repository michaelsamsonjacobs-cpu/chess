"""Public package surface for the ChessGuard toolkit.

This merges:
- Research/analytics APIs (analysis, data_sources, detection, features)
- Engine/service/preprocessing APIs
- Config/pipeline APIs
"""

from __future__ import annotations

import importlib

_LAZY_SUBMODULES = {
    "analysis",
    "data_sources",
    "detection",
    "features",
    "data",
    "training",
}

# --- Feature-branch public API ----------------------------------------------
from .engine import ChessGuardEngine, EngineResult  # noqa: F401
from .model import ThreatModel, load_default_model  # noqa: F401
from .models import (  # noqa: F401
    DetectionModel,
    HybridLogisticModel,
    ModelResult,
    RuleBasedModel,
)
from .pipeline.detection import DetectionPipeline, DetectionReport  # noqa: F401
from .preprocessing import PreprocessedGame, RawGame, preprocess_game  # noqa: F401
from .service import (  # noqa: F401
    ChessGuardService,
    TournamentEvaluationRequest,
    TournamentEvaluationResponse,
    TournamentGameEvaluation,
    TournamentGameInput,
)

# --- Main-branch public API -------------------------------------------------
from .config import (  # noqa: F401
    DEFAULT_ENGINE_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    EngineConfig,
    ModelConfig,
    PipelineConfig,
    ThresholdConfig,
)
from .engine import Engine  # noqa: F401
from .pipeline import AnalysisPipeline  # noqa: F401

# --- What `from chessguard import *` exposes --------------------------------
__all__ = [
    # Research/analytics subpackages
    "analysis",
    "data_sources",
    "detection",
    "features",
    "data",
    "training",

    # Feature-branch API
    "ChessGuardEngine",
    "EngineResult",
    "DetectionModel",
    "DetectionPipeline",
    "DetectionReport",
    "HybridLogisticModel",
    "ThreatModel",
    "load_default_model",
    "PreprocessedGame",
    "RawGame",
    "preprocess_game",
    "ChessGuardService",
    "TournamentEvaluationRequest",
    "TournamentEvaluationResponse",
    "TournamentGameEvaluation",
    "TournamentGameInput",

    # Main-branch API
    "AnalysisPipeline",
    "DEFAULT_ENGINE_CONFIG",
    "DEFAULT_PIPELINE_CONFIG",
    "Engine",
    "EngineConfig",
    "ModelResult",
    "ModelConfig",
    "PipelineConfig",
    "ThresholdConfig",
    "RuleBasedModel",
]


def __getattr__(name: str):  # pragma: no cover - simple lazy import helper
    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__version__ = "0.1.0"
