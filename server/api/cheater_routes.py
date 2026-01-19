"""
Known Cheater Database API Routes

Endpoints for checking and managing the banned player database.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db
from server.services import cheater_db


cheater_router = APIRouter(prefix="/api/cheaters", tags=["cheaters"])


class BanStatusResponse(BaseModel):
    """Response for ban status check."""
    username: str
    platform: str
    is_banned: bool
    ban_type: Optional[str]
    ban_date: Optional[str]
    ban_reason: Optional[str]
    source: Optional[str]


class BannedPlayerResponse(BaseModel):
    """Response for a banned player record."""
    id: int
    username: str
    platform: str
    ban_type: str
    ban_date: Optional[str]
    ban_reason: Optional[str]
    source: str
    first_seen: str
    is_active: bool

    class Config:
        from_attributes = True


class AddBanRequest(BaseModel):
    """Request to add a banned player."""
    username: str
    platform: str
    ban_type: str = "manual"
    ban_reason: Optional[str] = None


class ImportRequest(BaseModel):
    """Request to bulk import banned players."""
    usernames: List[str]
    platform: str
    ban_type: str = "imported"


class StatsResponse(BaseModel):
    """Database statistics."""
    total: int
    by_platform: dict
    by_type: dict


@cheater_router.get("/check/{platform}/{username}", response_model=BanStatusResponse)
def check_player_ban(
    platform: str,
    username: str,
    live: bool = Query(False, description="Check Lichess API live"),
    db: Session = Depends(get_db),
):
    """Check if a player is in the banned database."""
    
    # First check our database
    status = cheater_db.check_player(db=db, username=username, platform=platform)
    
    # If not found and live check requested for Lichess
    if not status.is_banned and live and platform == "lichess":
        status = cheater_db.check_player_live_lichess(username)
        
        # If banned, add to our database
        if status.is_banned:
            cheater_db.add_banned_player(
                db=db,
                username=username,
                platform=platform,
                ban_type=status.ban_type or "unknown",
                source="lichess_api_live",
                ban_reason=status.ban_reason,
            )
            db.commit()
    
    return BanStatusResponse(
        username=status.username,
        platform=status.platform,
        is_banned=status.is_banned,
        ban_type=status.ban_type,
        ban_date=status.ban_date.isoformat() if status.ban_date else None,
        ban_reason=status.ban_reason,
        source=status.source,
    )


@cheater_router.get("/recent", response_model=List[BannedPlayerResponse])
def get_recent_bans(
    platform: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Get recently added banned players."""
    banned = cheater_db.get_recent_bans(db=db, platform=platform, limit=limit)
    
    return [
        BannedPlayerResponse(
            id=b.id,
            username=b.username,
            platform=b.platform,
            ban_type=b.ban_type,
            ban_date=b.ban_date.isoformat() if b.ban_date else None,
            ban_reason=b.ban_reason,
            source=b.source,
            first_seen=b.first_seen.isoformat(),
            is_active=b.is_active,
        )
        for b in banned
    ]


@cheater_router.post("/add", response_model=BannedPlayerResponse)
def add_banned_player(
    request: AddBanRequest,
    db: Session = Depends(get_db),
):
    """Add a player to the banned database."""
    banned = cheater_db.add_banned_player(
        db=db,
        username=request.username,
        platform=request.platform,
        ban_type=request.ban_type,
        source="manual",
        ban_reason=request.ban_reason,
    )
    db.commit()
    
    return BannedPlayerResponse(
        id=banned.id,
        username=banned.username,
        platform=banned.platform,
        ban_type=banned.ban_type,
        ban_date=banned.ban_date.isoformat() if banned.ban_date else None,
        ban_reason=banned.ban_reason,
        source=banned.source,
        first_seen=banned.first_seen.isoformat(),
        is_active=banned.is_active,
    )


@cheater_router.post("/import")
def import_banned_players(
    request: ImportRequest,
    db: Session = Depends(get_db),
):
    """Bulk import banned players."""
    count = cheater_db.import_from_list(
        db=db,
        usernames=request.usernames,
        platform=request.platform,
        ban_type=request.ban_type,
        source="api_import",
    )
    
    return {"imported": count}


@cheater_router.get("/stats", response_model=StatsResponse)
def get_ban_stats(db: Session = Depends(get_db)):
    """Get statistics about the banned player database."""
    stats = cheater_db.get_ban_stats(db)
    return StatsResponse(**stats)
