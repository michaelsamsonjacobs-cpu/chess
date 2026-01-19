"""Public analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_public_service
from ..schemas.analyze import URLAnalyzeRequest, URLAnalyzeResponse
from ..services.public import PublicAnalysisService

router = APIRouter(tags=["public"])


@router.post("/analyze/url", response_model=URLAnalyzeResponse)
async def analyze_url(
    payload: URLAnalyzeRequest,
    service: PublicAnalysisService = Depends(get_public_service),
) -> URLAnalyzeResponse:
    return service.analyze_url(payload)

