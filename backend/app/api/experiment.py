"""API routes for the controlled experiment portal."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_experiment_service
from ..schemas.experiment import (
    ExperimentCompletionRequest,
    ExperimentExport,
    ExperimentSession,
    ExperimentSessionRequest,
)
from ..services.experiment import ExperimentService

router = APIRouter(prefix="/experiment", tags=["experiment"])


@router.post("/session", response_model=ExperimentSession)
async def start_experiment_session(
    payload: ExperimentSessionRequest,
    service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentSession:
    return service.start_session(payload)


@router.post("/session/{session_id}/complete", response_model=ExperimentExport)
async def complete_experiment_session(
    session_id: UUID,
    payload: ExperimentCompletionRequest,
    service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentExport:
    try:
        return service.complete_session(session_id, payload.pgn, payload.move_labels)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/session/{session_id}/export", response_model=ExperimentExport)
async def export_experiment_session(
    session_id: UUID,
    service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentExport:
    try:
        return service.get_export(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

