"""API routes for dataset management and training orchestration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_dataset_service
from ..schemas.dataset import DatasetDescriptor, DatasetRegisterRequest, ModelTrainingRequest, TrainingJobStatus
from ..services.dataset import DatasetService

router = APIRouter(tags=["datasets"])


@router.post("/datasets", response_model=DatasetDescriptor)
async def register_dataset(
    payload: DatasetRegisterRequest,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetDescriptor:
    return service.register_dataset(payload)


@router.get("/datasets", response_model=list[DatasetDescriptor])
async def list_datasets(service: DatasetService = Depends(get_dataset_service)) -> list[DatasetDescriptor]:
    return service.list_datasets()


@router.post("/models/{model_name}/train", response_model=TrainingJobStatus)
async def trigger_training(
    model_name: str,
    payload: ModelTrainingRequest,
    service: DatasetService = Depends(get_dataset_service),
) -> TrainingJobStatus:
    return service.trigger_training(model_name, payload)

