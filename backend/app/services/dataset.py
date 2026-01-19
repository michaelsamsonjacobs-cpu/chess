"""Services for dataset registration and model training orchestration."""

from __future__ import annotations

from typing import Dict, List
from uuid import UUID, uuid4

from ..repositories import AppRepositories
from ..schemas.dataset import DatasetDescriptor, DatasetRegisterRequest, ModelTrainingRequest, TrainingJobStatus


class DatasetService:
    """Manages dataset metadata and mock training jobs."""

    def __init__(self, repositories: AppRepositories) -> None:
        self._repositories = repositories
        self._training_jobs: Dict[UUID, TrainingJobStatus] = {}

    def register_dataset(self, request: DatasetRegisterRequest) -> DatasetDescriptor:
        descriptor = DatasetDescriptor(
            dataset_id=uuid4(),
            name=request.name,
            kind=request.kind,
            storage_uri=request.storage_uri,
            record_count=request.record_count,
            metadata=request.metadata,
        )
        self._repositories.datasets.add(descriptor)
        return descriptor

    def list_datasets(self) -> List[DatasetDescriptor]:
        return self._repositories.datasets.list()

    def trigger_training(self, model_name: str, request: ModelTrainingRequest) -> TrainingJobStatus:
        job = TrainingJobStatus(
            job_id=uuid4(),
            model_name=model_name,
            status="queued",
            details={"dataset_ids": ",".join(str(dataset_id) for dataset_id in request.dataset_ids)},
        )
        self._training_jobs[job.job_id] = job
        return job

    def get_training_jobs(self) -> List[TrainingJobStatus]:
        return list(self._training_jobs.values())

