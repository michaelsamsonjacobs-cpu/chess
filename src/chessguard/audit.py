"""Audit logging utilities for ChessGuard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from .models import AuditEvent


class AuditLogger:
    """Append-only JSONL audit logger suitable for tournament operations."""

    def __init__(self, file_path: str = "logs/audit.log") -> None:
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(
        self,
        actor: str,
        action: str,
        resource: str,
        status_code: int,
        latency_ms: float,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            actor=actor,
            action=action,
            resource=resource,
            status_code=status_code,
            latency_ms=latency_ms,
            detail=detail or {},
        )
        self._append(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _append(self, event: AuditEvent) -> None:
        payload = event.json()
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
