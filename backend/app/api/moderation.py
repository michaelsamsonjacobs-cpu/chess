"""API routes for moderation workflows."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_moderation_service
from ..schemas.moderation import ModerationLabel, ModerationLabelRequest, ModerationQueueEntry
from ..services.moderation import ModerationService

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.post("/labels", response_model=ModerationLabel)
async def add_label(
    payload: ModerationLabelRequest,
    service: ModerationService = Depends(get_moderation_service),
) -> ModerationLabel:
    return service.add_label(payload)


@router.get("/labels", response_model=list[ModerationLabel])
async def list_labels(service: ModerationService = Depends(get_moderation_service)) -> list[ModerationLabel]:
    return service.list_labels()


@router.post("/queue", response_model=ModerationQueueEntry)
async def enqueue_review(
    payload: ModerationQueueEntry,
    service: ModerationService = Depends(get_moderation_service),
) -> ModerationQueueEntry:
    return service.enqueue_review(payload)


@router.get("/queue", response_model=list[ModerationQueueEntry])
async def get_queue(service: ModerationService = Depends(get_moderation_service)) -> list[ModerationQueueEntry]:
    return service.get_queue()

