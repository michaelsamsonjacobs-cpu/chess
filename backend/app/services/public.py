"""Services powering public-facing lightweight endpoints."""

from __future__ import annotations

from uuid import uuid4

from ..schemas.analyze import URLAnalyzeRequest, URLAnalyzeResponse


class PublicAnalysisService:
    """Performs lightweight URL-based analysis requests."""

    def analyze_url(self, request: URLAnalyzeRequest) -> URLAnalyzeResponse:
        reference_id = str(uuid4())
        message = (
            "Queued analysis for provided resource; results will be available via the admin dashboard."
        )
        return URLAnalyzeResponse(
            reference_id=reference_id,
            kind=request.kind,
            status="queued",
            message=message,
        )

