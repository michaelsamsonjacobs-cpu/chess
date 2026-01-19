"""API routes for game ingestion and analytics."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_game_service, get_repositories
from ..repositories import AppRepositories
from ..schemas.game import GameAnalysis, GameIngestRequest, GameIngestResponse, GameReport
from ..services.game_analysis import GameService

router = APIRouter(prefix="/games", tags=["games"])


@router.post("/ingest", response_model=GameIngestResponse)
async def ingest_game(
    payload: GameIngestRequest,
    service: GameService = Depends(get_game_service),
) -> GameIngestResponse:
    try:
        analysis = service.ingest_game(payload)
    except ValueError as exc:  # pragma: no cover - FastAPI will convert to JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GameIngestResponse(game_id=analysis.game_id, analysis=analysis)


@router.get("/{game_id}/features", response_model=GameAnalysis)
async def get_game_features(
    game_id: UUID,
    repositories: AppRepositories = Depends(get_repositories),
) -> GameAnalysis:
    try:
        record = repositories.games.get(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return record.analysis


@router.get("/{game_id}/report", response_model=GameReport)
async def get_game_report(
    game_id: UUID,
    service: GameService = Depends(get_game_service),
) -> GameReport:
    try:
        return service.get_report(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

