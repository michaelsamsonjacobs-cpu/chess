"""Schemas describing datasets curated by ChessGuard."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .common import AuditMetadata


class DatasetRegisterRequest(BaseModel):
    """Request payload for registering a dataset artifact."""

    name: str = Field(..., description="Human readable dataset identifier.")
    kind: str = Field(..., description="Dataset type such as engine_pure or hybrid_assist.")
    storage_uri: str = Field(..., description="Location of the dataset in S3 or Hugging Face.")
    metadata: Dict[str, str] = Field(default_factory=dict)
    record_count: Optional[int] = Field(None, ge=0)


class DatasetDescriptor(BaseModel):
    """Metadata describing a stored dataset."""

    dataset_id: UUID
    name: str
    kind: str
    storage_uri: str
    record_count: Optional[int] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    audit: AuditMetadata = Field(default_factory=AuditMetadata)


class ModelTrainingRequest(BaseModel):
    """Request to trigger model training on a dataset or configuration."""

    dataset_ids: List[UUID] = Field(..., description="Datasets to include when training the model.")
    hyperparameters: Dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = Field(None)


class TrainingJobStatus(BaseModel):
    """Represents the status of a training job."""

    job_id: UUID
    model_name: str
    status: str = Field(..., description="queued, running, completed, failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, str] = Field(default_factory=dict)

