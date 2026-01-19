"""FastAPI dependency helpers for ChessGuard."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, selectinload

from .database import get_db
from .models import LichessAccount
from .security import decode_access_token
from .services.lichess import LichessService

# Instantiate the service once so it can be reused by all requests.
lichess_service = LichessService()
bearer_scheme = HTTPBearer(auto_error=False)


def get_lichess_service() -> LichessService:
    """Provide the shared Lichess service instance."""

    return lichess_service


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> LichessAccount:
    """Validate the bearer token and load the user's integration state."""

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    token = credentials.credentials.strip()
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        user_id = int(subject)
    except (jwt.PyJWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from None

    account = (
        db.query(LichessAccount)
        .options(selectinload(LichessAccount.games), selectinload(LichessAccount.reports))
        .filter(LichessAccount.user_id == user_id)
        .first()
    )
    if account is None:
        account = LichessAccount(user_id=user_id)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def require_connected_user(
    user: LichessAccount = Depends(get_current_user),
) -> LichessAccount:
    """Ensure that the user has already connected their Lichess account."""

    if not user.access_token or not user.lichess_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect your Lichess account before performing this action.",
        )
    return user
