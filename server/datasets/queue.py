"""Dataset session queue management for generating labelled training data."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

__all__ = ["SessionSpec", "SessionQueue"]


@dataclass
class SessionSpec:
    """Represents a queued game generation job."""

    id: str
    session_type: str
    label: str
    status: str
    created_at: str
    config: Dict[str, object] = field(default_factory=dict)
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "session_type": self.session_type,
            "label": self.label,
            "status": self.status,
            "created_at": self.created_at,
            "config": dict(self.config),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def create(
        cls,
        session_type: str,
        label: str,
        *,
        status: str = "pending",
        config: Optional[Dict[str, object]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> "SessionSpec":
        return cls(
            id=str(uuid.uuid4()),
            session_type=session_type,
            label=label,
            status=status,
            created_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            config=config or {},
            metadata=metadata or {},
        )


class SessionQueue:
    """Simple JSON file backed queue used to orchestrate game generation."""

    def __init__(self, storage_path: Path | str = "var/session_queue.json") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.storage_path.exists():
            self._write([])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enqueue(self, session: SessionSpec) -> SessionSpec:
        with self._lock:
            data = self._read()
            data.append(session.to_dict())
            self._write(data)
        return session

    def bulk_enqueue(self, sessions: Iterable[SessionSpec]) -> List[SessionSpec]:
        sessions = list(sessions)
        with self._lock:
            data = self._read()
            data.extend(session.to_dict() for session in sessions)
            self._write(data)
        return sessions

    def list(self, status: Optional[str] = None) -> List[SessionSpec]:
        data = self._read()
        specs = [SessionSpec(**item) for item in data]
        if status:
            specs = [spec for spec in specs if spec.status == status]
        return specs

    def update_status(self, session_id: str, status: str) -> Optional[SessionSpec]:
        with self._lock:
            data = self._read()
            updated: Optional[SessionSpec] = None
            for entry in data:
                if entry["id"] == session_id:
                    entry["status"] = status
                    updated = SessionSpec(**entry)
                    break
            if updated is not None:
                self._write(data)
            return updated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _read(self) -> List[Dict[str, object]]:
        if not self.storage_path.exists():
            return []
        raw = self.storage_path.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        return json.loads(raw)

    def _write(self, data: List[Dict[str, object]]) -> None:
        payload = json.dumps(data, indent=2, sort_keys=True)
        self.storage_path.write_text(payload + "\n", encoding="utf-8")
