"""Schemas for lightweight public analysis endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class URLAnalyzeRequest(BaseModel):
    """Request body to trigger analysis of a remote resource."""

    url: HttpUrl
    kind: str = Field("game", description="Resource type: game or profile.")
    notes: Optional[str] = Field(None)


class URLAnalyzeResponse(BaseModel):
    """Response returned by the /analyze/url endpoint."""

    reference_id: str
    kind: str
    status: str
    message: str

