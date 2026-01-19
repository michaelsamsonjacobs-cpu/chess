"""Public models exposed by the ChessGuard package.

This module unifies the legacy detection models with the API schemas so that
callers can import from ``chessguard.models`` regardless of whether they are
running analytical notebooks or the service backend.
"""

from __future__ import annotations

from .api import Alert, AuditEvent, LiveGame, LivePGNSubmission, ModelExplanation, RiskAssessment
from .base import DetectionModel, ModelResult
from .baseline import RuleBasedModel
from .hybrid import HybridLogisticModel

__all__ = [
    "Alert",
    "AuditEvent",
    "DetectionModel",
    "HybridLogisticModel",
    "LiveGame",
    "LivePGNSubmission",
    "ModelExplanation",
    "ModelResult",
    "RiskAssessment",
    "RuleBasedModel",
]
