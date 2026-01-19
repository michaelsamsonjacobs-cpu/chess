"""API routes for profile-level analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_profile_service, get_repositories
from ..repositories import AppRepositories
from ..schemas.profile import ProfileAnalytics, ProfileIngestRequest, ProfileReport
from ..services.profile_analysis import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("/ingest", response_model=ProfileAnalytics)
async def ingest_profile(
    payload: ProfileIngestRequest,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileAnalytics:
    return service.ingest_profile(payload)


@router.get("/{profile_id}/analytics", response_model=ProfileAnalytics)
async def get_profile_analytics(
    profile_id: str,
    repositories: AppRepositories = Depends(get_repositories),
) -> ProfileAnalytics:
    try:
        return repositories.profiles.get(profile_id).analytics
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{profile_id}/report", response_model=ProfileReport)
async def get_profile_report(
    profile_id: str,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileReport:
    try:
        return service.get_report(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

