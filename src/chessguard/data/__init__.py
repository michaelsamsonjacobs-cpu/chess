"""Data ingestion and labeling utilities for ChessGuard."""

from .ingest import (
    TrustedSource,
    FieldSpec,
    TRUSTED_SOURCES,
    register_trusted_source,
    get_trusted_source,
    ingest_trusted_source,
    parse_pgn_records,
    parse_json_records,
)
from .labeling import (
    EngineEvaluation,
    LabelingGuidelines,
    SimpleHeuristicEvaluator,
    annotate_games_with_labels,
    enrich_with_engine_evaluations,
)
from .loader import load_pgn_games, load_single_game, load_telemetry
from .telemetry import MoveTiming, SessionTelemetry

__all__ = [
    "TrustedSource",
    "FieldSpec",
    "TRUSTED_SOURCES",
    "register_trusted_source",
    "get_trusted_source",
    "ingest_trusted_source",
    "parse_pgn_records",
    "parse_json_records",
    "EngineEvaluation",
    "LabelingGuidelines",
    "SimpleHeuristicEvaluator",
    "annotate_games_with_labels",
    "enrich_with_engine_evaluations",
    "load_pgn_games",
    "load_single_game",
    "load_telemetry",
    "MoveTiming",
    "SessionTelemetry",
]
