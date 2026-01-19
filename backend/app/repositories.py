"""In-memory repositories backing the ChessGuard prototype implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List
from uuid import UUID

from .schemas.dataset import DatasetDescriptor
from .schemas.experiment import ExperimentExport, ExperimentSession
from .schemas.game import GameAnalysis, GameIngestRequest, GameRecord
from .schemas.moderation import ModerationLabel, ModerationQueueEntry
from .schemas.profile import ProfileAnalytics, ProfileIngestRequest, ProfileRecord


class GameRepository:
    """Repository storing ingested games and their analyses."""

    def __init__(self) -> None:
        self._records: Dict[UUID, GameRecord] = {}

    def upsert(self, record: GameRecord) -> GameRecord:
        self._records[record.id] = record
        return record

    def create(self, request: GameIngestRequest, analysis: GameAnalysis) -> GameRecord:
        record = GameRecord(id=analysis.game_id, request=request, analysis=analysis)
        return self.upsert(record)

    def get(self, game_id: UUID) -> GameRecord:
        record = self._records.get(game_id)
        if not record:
            raise KeyError(f"Game {game_id} not found")
        return record

    def list(self) -> Iterable[GameRecord]:
        return self._records.values()


class ProfileRepository:
    """Repository storing aggregated profiles."""

    def __init__(self) -> None:
        self._records: Dict[str, ProfileRecord] = {}

    def upsert(self, record: ProfileRecord) -> ProfileRecord:
        self._records[record.id] = record
        return record

    def create(self, request: ProfileIngestRequest, analytics: ProfileAnalytics) -> ProfileRecord:
        record = ProfileRecord(id=analytics.profile_id, request=request, analytics=analytics)
        return self.upsert(record)

    def get(self, profile_id: str) -> ProfileRecord:
        record = self._records.get(profile_id)
        if not record:
            raise KeyError(f"Profile {profile_id} not found")
        return record

    def list(self) -> Iterable[ProfileRecord]:
        return self._records.values()


class ExperimentRepository:
    """Repository storing experiment sessions and exports."""

    def __init__(self) -> None:
        self._sessions: Dict[UUID, ExperimentSession] = {}
        self._exports: Dict[UUID, ExperimentExport] = {}

    def save_session(self, session: ExperimentSession) -> ExperimentSession:
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: UUID) -> ExperimentSession:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")
        return session

    def save_export(self, export: ExperimentExport) -> ExperimentExport:
        self._exports[export.session_id] = export
        return export

    def get_export(self, session_id: UUID) -> ExperimentExport:
        export = self._exports.get(session_id)
        if not export:
            raise KeyError(f"No export available for session {session_id}")
        return export


class DatasetRepository:
    """Repository for dataset descriptors."""

    def __init__(self) -> None:
        self._datasets: Dict[UUID, DatasetDescriptor] = {}

    def add(self, descriptor: DatasetDescriptor) -> DatasetDescriptor:
        self._datasets[descriptor.dataset_id] = descriptor
        return descriptor

    def get(self, dataset_id: UUID) -> DatasetDescriptor:
        descriptor = self._datasets.get(dataset_id)
        if not descriptor:
            raise KeyError(f"Dataset {dataset_id} not found")
        return descriptor

    def list(self) -> List[DatasetDescriptor]:
        return list(self._datasets.values())


class ModerationRepository:
    """Repository storing moderation labels and queue entries."""

    def __init__(self) -> None:
        self._labels: Dict[UUID, ModerationLabel] = {}
        self._queue: List[ModerationQueueEntry] = []

    def add_label(self, label: ModerationLabel) -> ModerationLabel:
        self._labels[label.label_id] = label
        return label

    def list_labels(self) -> List[ModerationLabel]:
        return list(self._labels.values())

    def add_queue_entry(self, entry: ModerationQueueEntry) -> None:
        self._queue.append(entry)

    def get_queue(self) -> List[ModerationQueueEntry]:
        return list(self._queue)


@dataclass
class AppRepositories:
    """Container bundling all repositories for dependency injection."""

    games: GameRepository = field(default_factory=GameRepository)
    profiles: ProfileRepository = field(default_factory=ProfileRepository)
    experiments: ExperimentRepository = field(default_factory=ExperimentRepository)
    datasets: DatasetRepository = field(default_factory=DatasetRepository)
    moderation: ModerationRepository = field(default_factory=ModerationRepository)

