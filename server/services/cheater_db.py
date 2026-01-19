"""
Known Cheater Database Service

Cross-references players against known banned accounts from
Lichess, Chess.com, and other sources.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

import requests
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from server.models.banned_player import BannedPlayer


@dataclass
class BanStatus:
    """Ban status check result."""
    username: str
    platform: str
    is_banned: bool
    ban_type: Optional[str]
    ban_date: Optional[datetime]
    ban_reason: Optional[str]
    source: Optional[str]
    
    def to_dict(self) -> Dict:
        return {
            "username": self.username,
            "platform": self.platform,
            "is_banned": self.is_banned,
            "ban_type": self.ban_type,
            "ban_date": self.ban_date.isoformat() if self.ban_date else None,
            "ban_reason": self.ban_reason,
            "source": self.source,
        }


def check_player(
    db: Session,
    username: str,
    platform: str,
) -> BanStatus:
    """
    Check if a player is in the known cheater database.
    
    Returns BanStatus with is_banned=False if not found.
    """
    stmt = (
        select(BannedPlayer)
        .where(
            and_(
                BannedPlayer.username == username.lower(),
                BannedPlayer.platform == platform,
                BannedPlayer.is_active == True,
            )
        )
    )
    
    banned = db.execute(stmt).scalar_one_or_none()
    
    if banned:
        return BanStatus(
            username=username,
            platform=platform,
            is_banned=True,
            ban_type=banned.ban_type,
            ban_date=banned.ban_date,
            ban_reason=banned.ban_reason,
            source=banned.source,
        )
    
    return BanStatus(
        username=username,
        platform=platform,
        is_banned=False,
        ban_type=None,
        ban_date=None,
        ban_reason=None,
        source=None,
    )


def check_player_live_lichess(username: str) -> BanStatus:
    """
    Check Lichess API directly for current TOS violation status.
    
    This is a live check, not from our database.
    """
    try:
        response = requests.get(
            f"https://lichess.org/api/user/{username}",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        
        if response.status_code == 404:
            return BanStatus(
                username=username,
                platform="lichess",
                is_banned=False,
                ban_type=None,
                ban_date=None,
                ban_reason="Account not found",
                source="lichess_api_live",
            )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for TOS violation (marked/closed account)
            if data.get("tosViolation", False):
                return BanStatus(
                    username=username,
                    platform="lichess",
                    is_banned=True,
                    ban_type="tos_violation",
                    ban_date=None,  # Lichess doesn't provide ban date
                    ban_reason="Terms of Service violation",
                    source="lichess_api_live",
                )
            
            # Check for closed account
            if data.get("closed", False) or data.get("disabled", False):
                return BanStatus(
                    username=username,
                    platform="lichess",
                    is_banned=True,
                    ban_type="account_closed",
                    ban_date=None,
                    ban_reason="Account closed/disabled",
                    source="lichess_api_live",
                )
        
        return BanStatus(
            username=username,
            platform="lichess",
            is_banned=False,
            ban_type=None,
            ban_date=None,
            ban_reason=None,
            source="lichess_api_live",
        )
        
    except Exception as e:
        # On error, return unknown status
        return BanStatus(
            username=username,
            platform="lichess",
            is_banned=False,
            ban_type=None,
            ban_date=None,
            ban_reason=f"API check failed: {str(e)}",
            source="lichess_api_error",
        )


def add_banned_player(
    db: Session,
    username: str,
    platform: str,
    ban_type: str,
    source: str,
    ban_date: Optional[datetime] = None,
    ban_reason: Optional[str] = None,
) -> BannedPlayer:
    """Add a player to the banned database."""
    
    # Check if already exists
    existing = db.execute(
        select(BannedPlayer)
        .where(
            and_(
                BannedPlayer.username == username.lower(),
                BannedPlayer.platform == platform,
            )
        )
    ).scalar_one_or_none()
    
    if existing:
        # Update existing record
        existing.ban_type = ban_type
        existing.source = source
        existing.ban_date = ban_date or existing.ban_date
        existing.ban_reason = ban_reason or existing.ban_reason
        existing.last_verified = datetime.utcnow()
        existing.is_active = True
        db.flush()
        return existing
    
    # Create new record
    banned = BannedPlayer(
        username=username.lower(),
        platform=platform,
        ban_type=ban_type,
        ban_date=ban_date,
        ban_reason=ban_reason,
        source=source,
        first_seen=datetime.utcnow(),
        last_verified=datetime.utcnow(),
        is_active=True,
    )
    db.add(banned)
    db.flush()
    return banned


def sync_from_lichess_live(
    db: Session,
    username: str,
) -> Optional[BannedPlayer]:
    """
    Check Lichess live and add to database if banned.
    
    Returns BannedPlayer if player is banned, None otherwise.
    """
    status = check_player_live_lichess(username)
    
    if status.is_banned:
        return add_banned_player(
            db=db,
            username=username,
            platform="lichess",
            ban_type=status.ban_type or "unknown",
            source="lichess_api_live",
            ban_date=status.ban_date,
            ban_reason=status.ban_reason,
        )
    
    return None


def import_from_list(
    db: Session,
    usernames: List[str],
    platform: str,
    ban_type: str = "imported",
    source: str = "manual_import",
) -> int:
    """
    Bulk import a list of banned usernames.
    
    Returns count of players added.
    """
    count = 0
    for username in usernames:
        username = username.strip().lower()
        if not username:
            continue
        
        add_banned_player(
            db=db,
            username=username,
            platform=platform,
            ban_type=ban_type,
            source=source,
        )
        count += 1
    
    db.commit()
    return count


def get_recent_bans(
    db: Session,
    platform: Optional[str] = None,
    limit: int = 50,
) -> List[BannedPlayer]:
    """Get recently added banned players."""
    stmt = select(BannedPlayer).order_by(BannedPlayer.first_seen.desc()).limit(limit)
    
    if platform:
        stmt = stmt.where(BannedPlayer.platform == platform)
    
    return list(db.execute(stmt).scalars().all())


def get_ban_stats(db: Session) -> Dict:
    """Get statistics about the banned player database."""
    from sqlalchemy import func
    
    total = db.execute(
        select(func.count(BannedPlayer.id))
    ).scalar() or 0
    
    by_platform = {}
    for platform in ["lichess", "chesscom"]:
        count = db.execute(
            select(func.count(BannedPlayer.id))
            .where(BannedPlayer.platform == platform)
        ).scalar() or 0
        by_platform[platform] = count
    
    by_type = {}
    types = db.execute(
        select(BannedPlayer.ban_type, func.count(BannedPlayer.id))
        .group_by(BannedPlayer.ban_type)
    ).all()
    for ban_type, count in types:
        by_type[ban_type] = count
    
    return {
        "total": total,
        "by_platform": by_platform,
        "by_type": by_type,
    }
