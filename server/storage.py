"""Simple in-memory data storage used by the demo backend."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional


@dataclass
class ReportRecord:
    """Represents a single cheat report submission."""

    game_id: str
    player_id: str
    reason: str
    description: Optional[str]
    created_at: datetime
    status_code: int
    message: Optional[str] = None


@dataclass
class UserAccount:
    """Stores the Lichess integration state for a user."""

    user_id: str
    lichess_username: Optional[str] = None
    lichess_token: Optional[str] = None
    last_synced: Optional[datetime] = None
    games: List[Dict[str, object]] = field(default_factory=list)
    reports: List[ReportRecord] = field(default_factory=list)


class InMemoryUserStore:
    """Thread-safe storage for user information used by this demo project."""

    def __init__(self) -> None:
        self._users: Dict[str, UserAccount] = {}
        self._lock = Lock()

    def get_or_create(self, user_id: str) -> UserAccount:
        """Return an existing user or create a blank record."""

        with self._lock:
            if user_id not in self._users:
                self._users[user_id] = UserAccount(user_id=user_id)
            return self._users[user_id]

    def set_credentials(self, user_id: str, username: str, token: str) -> UserAccount:
        """Persist Lichess credentials for the user."""

        with self._lock:
            user = self.get_or_create(user_id)
            user.lichess_username = username
            user.lichess_token = token
            return user

    def update_games(self, user_id: str, games: List[Dict[str, object]]) -> UserAccount:
        """Replace the stored games for a user and timestamp the sync."""

        with self._lock:
            user = self.get_or_create(user_id)
            user.games = list(games)
            user.last_synced = datetime.now(timezone.utc)
            return user

    def add_report(
        self,
        user_id: str,
        *,
        game_id: str,
        player_id: str,
        reason: str,
        description: Optional[str],
        status_code: int,
        message: Optional[str] = None,
    ) -> ReportRecord:
        """Add a cheat report entry to the user's history."""

        record = ReportRecord(
            game_id=game_id,
            player_id=player_id,
            reason=reason,
            description=description,
            created_at=datetime.now(timezone.utc),
            status_code=status_code,
            message=message,
        )
        with self._lock:
            user = self.get_or_create(user_id)
            user.reports.append(record)
        return record

    def snapshot(self, user_id: str) -> UserAccount:
        """Return a deep copy of the user state for safe read operations."""

        with self._lock:
            user = self.get_or_create(user_id)
            return deepcopy(user)


user_store = InMemoryUserStore()
"""Global instance used by the application."""
