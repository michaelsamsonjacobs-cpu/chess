"""FastAPI service exposing ChessGuard risk assessments and alerts."""

from __future__ import annotations

import time
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from chessguard.analytics import RiskEngine
from chessguard.audit import AuditLogger
from chessguard.models import Alert, LivePGNSubmission, ModelExplanation, RiskAssessment
from chessguard.security import APIKeyAuthenticator, APIUser
from chessguard.storage import GameRepository


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
app = FastAPI(title="ChessGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

repository = GameRepository()
risk_engine = RiskEngine()
authenticator = APIKeyAuthenticator()
audit_logger = AuditLogger()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, authenticator: APIKeyAuthenticator, exempt_paths: Optional[List[str]] = None) -> None:
        super().__init__(app)
        self.authenticator = authenticator
        self.exempt_paths = set(exempt_paths or [])

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path.startswith("/docs")
            or path.startswith("/openapi")
            or path.startswith("/redoc")
            or path in self.exempt_paths
            or request.method.upper() == "OPTIONS"
        ):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        try:
            user = self.authenticator.authenticate(api_key)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        request.state.user = user
        return await call_next(request)


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, audit_logger: AuditLogger) -> None:
        super().__init__(app)
        self.audit_logger = audit_logger

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            actor = getattr(request.state, "user", None)
            actor_label = actor.actor_label if isinstance(actor, APIUser) else "anonymous"
            status_code = response.status_code if response is not None else 500
            self.audit_logger.record(
                actor=actor_label,
                action=request.method,
                resource=request.url.path,
                status_code=status_code,
                latency_ms=duration_ms,
                detail={
                    "query": dict(request.query_params),
                },
            )


app.add_middleware(AuthenticationMiddleware, authenticator=authenticator, exempt_paths=["/health"])
app.add_middleware(AuditMiddleware, audit_logger=audit_logger)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class SubmissionResponse(BaseModel):
    game_id: str
    risk: RiskAssessment
    explanation: ModelExplanation


class RiskResponse(BaseModel):
    game_id: str
    event_id: str
    player_id: str
    risk: RiskAssessment


class ExplanationResponse(BaseModel):
    game_id: str
    explanation: ModelExplanation


class AlertsResponse(BaseModel):
    alerts: List[Alert]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}


@app.post(
    "/games",
    response_model=SubmissionResponse,
    tags=["games"],
)
async def submit_game(
    submission: LivePGNSubmission,
    user: APIUser = Depends(authenticator.require_roles("director", "arbiter")),
):
    risk, explanation = risk_engine.assess(submission)
    record = repository.add_game(submission, risk, explanation, submitted_by=user.name)
    return SubmissionResponse(game_id=record.id, risk=risk, explanation=explanation)


@app.get(
    "/games/{game_id}/risk",
    response_model=RiskResponse,
    tags=["games"],
)
async def get_risk(
    game_id: str,
    user: APIUser = Depends(authenticator.require_roles("director", "monitor", "arbiter")),
):
    game = repository.get_game(game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return RiskResponse(game_id=game.id, event_id=game.event_id, player_id=game.player_id, risk=game.risk)


@app.get(
    "/games/{game_id}/explanation",
    response_model=ExplanationResponse,
    tags=["games"],
)
async def get_explanation(
    game_id: str,
    user: APIUser = Depends(authenticator.require_roles("director", "analyst", "arbiter")),
):
    game = repository.get_game(game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return ExplanationResponse(game_id=game.id, explanation=game.explanation)


@app.get(
    "/events/{event_id}/alerts",
    response_model=AlertsResponse,
    tags=["alerts"],
)
async def get_event_alerts(
    event_id: str,
    threshold: float = 70.0,
    user: APIUser = Depends(authenticator.require_roles("director", "monitor", "arbiter")),
):
    alerts = repository.get_alerts_for_event(event_id, threshold=threshold)
    return AlertsResponse(alerts=alerts)


@app.get(
    "/alerts",
    response_model=AlertsResponse,
    tags=["alerts"],
)
async def get_global_alerts(
    threshold: float = 70.0,
    limit: int = 20,
    user: APIUser = Depends(authenticator.require_roles("director", "monitor", "arbiter")),
):
    alerts = repository.get_global_alerts(threshold=threshold, limit=limit)
    return AlertsResponse(alerts=alerts)
