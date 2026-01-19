"""API routes that expose Lichess integration features."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, object_session

from ..database import get_db
from ..dependencies import get_current_user, get_lichess_service, require_connected_user
from ..legacy_app_models import (
    GameSummary,
    ReportRecordModel,
    SyncGamesResponse,
    UserStateResponse,
)
from ..models import (
    LichessAccount,
    LichessConnectRequest,
    LichessGame,
    LichessReport,
    LichessReportRequest,
    LichessReportResponse,
    SyncGamesRequest,
)
from ..services.lichess import LichessAPIError, LichessRateLimitError, LichessService

router = APIRouter(prefix="/api/lichess", tags=["lichess"])
logger = logging.getLogger(__name__)


def _reload_account(account: LichessAccount, session: Session) -> LichessAccount:
    if account not in session:
        session.add(account)
    session.refresh(account)
    # Trigger lazy loads so that callers always receive fresh data.
    # Note: selectinload in the dependency usually handles this, but
    # forcing a refresh ensures we have the latest state from DB.
    # We must ensure specific attributes are loaded if they were expired.
    _ = list(account.games)
    _ = list(account.reports)
    return account


def _serialize_user_state(account: LichessAccount) -> UserStateResponse:
    games = [GameSummary.model_validate(game.data) for game in account.games]
    reports: List[ReportRecordModel] = [
        ReportRecordModel(
            gameId=record.game_id,
            playerId=record.player_id,
            reason=record.reason,
            description=record.description,
            createdAt=record.created_at,
            statusCode=record.status_code,
            message=record.message,
        )
        for record in account.reports
    ]
    return UserStateResponse(
        userId=str(account.user_id),
        lichessUsername=account.lichess_username,
        connected=bool(account.access_token and account.lichess_username),
        lastSync=account.last_synced,
        games=games,
        reports=reports,
    )


@router.get("/state", response_model=UserStateResponse)
async def get_state(
    user: LichessAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserStateResponse:
    """Return the stored integration state for the active user."""

    account = _reload_account(user, db)
    return _serialize_user_state(account)


@router.post("/connect", response_model=UserStateResponse)
async def connect_account(
    payload: LichessConnectRequest,
    user: LichessAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserStateResponse:
    """Store the token and username that authorise Lichess requests."""

    logger.info("Linking Lichess account %s to user %s", payload.username, user.user_id)
    if user not in db:
        db.add(user)
    
    user.lichess_username = payload.username
    user.access_token = payload.access_token
    db.add(user)
    db.commit()
    account = _reload_account(user, db)
    return _serialize_user_state(account)


@router.post("/sync", response_model=SyncGamesResponse)
async def sync_games(
    request: SyncGamesRequest,
    user: LichessAccount = Depends(require_connected_user),
    service: LichessService = Depends(get_lichess_service),
    db: Session = Depends(get_db),
) -> SyncGamesResponse:
    """Fetch recent games from Lichess for the authenticated user."""

    assert user.access_token and user.lichess_username  # for static type checking

    try:
        games = await service.fetch_recent_games(
            user.lichess_username,
            user.access_token,
            max_games=request.max_games,
            since=request.since,
        )
    except LichessRateLimitError as exc:
        logger.warning("Rate limited by Lichess when syncing games: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests to Lichess. Please retry later.",
        ) from exc
    except LichessAPIError as exc:
        logger.exception("Failed to fetch games from Lichess: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch games from Lichess at this time.",
        ) from exc

    if user not in db:
        db.add(user)

    db.query(LichessGame).filter(LichessGame.account_id == user.id).delete(synchronize_session=False)
    for game in games:
        lichess_id = str(game.get("id"))
        db.add(
            LichessGame(account_id=user.id, lichess_id=lichess_id, data=game),
        )

    user.last_synced = datetime.utcnow()
    db.add(user)
    db.commit()
    db.expire(user, ["games"])

    return SyncGamesResponse(
        count=len(games),
        lastSync=user.last_synced,
        games=[GameSummary.model_validate(game) for game in games],
    )


@router.post("/report", response_model=LichessReportResponse)
async def report_cheating(
    payload: LichessReportRequest,
    user: LichessAccount = Depends(require_connected_user),
    service: LichessService = Depends(get_lichess_service),
    db: Session = Depends(get_db),
) -> LichessReportResponse:
    """Forward a cheat report to the Lichess moderation endpoint."""

    assert user.access_token  # narrow type for static checkers

    try:
        response = await service.submit_cheat_report(
            user.access_token,
            game_id=payload.game_id,
            player_id=payload.player_id,
            reason=payload.reason,
            description=payload.description,
        )
    except LichessRateLimitError as exc:
        logger.warning("Rate limited by Lichess when submitting report: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many report requests to Lichess. Please wait before retrying.",
        ) from exc
    except LichessAPIError as exc:
        logger.exception("Report submission failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lichess rejected the report submission.",
        ) from exc

    detail = response.get("detail")
    if isinstance(detail, (dict, list)):
        detail_message = json.dumps(detail)
    elif detail is None:
        detail_message = None
    else:
        detail_message = str(detail)

    if user not in db:
        db.add(user)

    record = LichessReport(
        account_id=user.id,
        game_id=payload.game_id,
        player_id=payload.player_id,
        reason=payload.reason,
        description=payload.description,
        status_code=response.get("status_code", 200),
        message=detail_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    report_model = ReportRecordModel(
        gameId=record.game_id,
        playerId=record.player_id,
        reason=record.reason,
        description=record.description,
        createdAt=record.created_at,
        statusCode=record.status_code,
        message=record.message,
    )
    return LichessReportResponse(status="submitted", report=report_model)
