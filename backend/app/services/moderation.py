"""Services for moderation workflows and human-in-the-loop review."""

from __future__ import annotations

from typing import List
from uuid import uuid4

from ..repositories import AppRepositories
from ..schemas.common import RiskFlag
from ..schemas.moderation import (
    ModerationLabel,
    ModerationLabelRequest,
    ModerationQueueEntry,
)


class ModerationService:
    """Handles moderation labels and queue management."""

    def __init__(self, repositories: AppRepositories) -> None:
        self._repositories = repositories

    def add_label(self, request: ModerationLabelRequest) -> ModerationLabel:
        label = ModerationLabel(
            label_id=uuid4(),
            target_id=request.target_id,
            target_type=request.target_type,
            label=request.label,
            confidence=request.confidence,
            notes=request.notes,
        )

        if request.label in {"engine_assist", "closed_account"} and request.confidence >= 0.8:
            label.flags.append(
                RiskFlag(
                    code="requires_review",
                    message="High confidence adverse label issued; ensure due process.",
                    severity="high",
                )
            )

        self._repositories.moderation.add_label(label)
        return label

    def list_labels(self) -> List[ModerationLabel]:
        return self._repositories.moderation.list_labels()

    def enqueue_review(self, entry: ModerationQueueEntry) -> ModerationQueueEntry:
        self._repositories.moderation.add_queue_entry(entry)
        return entry

    def get_queue(self) -> List[ModerationQueueEntry]:
        return self._repositories.moderation.get_queue()

