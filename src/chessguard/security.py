"""Authentication and authorization helpers for ChessGuard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Sequence

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader


API_KEY_HEADER_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


@dataclass
class APIUser:
    """Lightweight representation of an authenticated staff member."""

    key: str
    role: str
    name: str

    @property
    def actor_label(self) -> str:
        return f"{self.name} ({self.role})"


class APIKeyAuthenticator:
    """Validates API keys and enforces role-based access control."""

    def __init__(self, key_config: Optional[Dict[str, Dict[str, str]]] = None) -> None:
        self._keys = key_config or self._load_from_env()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def authenticate(self, api_key: Optional[str]) -> APIUser:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
            )
        record = self._keys.get(api_key)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return APIUser(key=api_key, role=record["role"], name=record["name"])

    def dependency(self) -> APIUser:
        return Depends(self._dependency_impl)

    async def _dependency_impl(self, api_key: Optional[str] = Depends(_api_key_header)) -> APIUser:
        return self.authenticate(api_key)

    def require_roles(self, *roles: str):
        normalized = {role.lower() for role in roles if role}

        async def dependency(user: APIUser = Depends(get_request_user)) -> APIUser:
            if normalized and user.role.lower() not in normalized:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )
            return user

        return dependency

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_from_env(self) -> Dict[str, Dict[str, str]]:
        env_value = os.getenv("CHESSGUARD_API_KEYS", "director|Chief Arbiter:director-key")
        keys: Dict[str, Dict[str, str]] = {}
        for entry in env_value.split(","):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            identifier, key = entry.split(":", 1)
            identifier = identifier.strip()
            key = key.strip()
            if not key:
                continue
            if "|" in identifier:
                role, name = [part.strip() for part in identifier.split("|", 1)]
            else:
                role, name = identifier, identifier.title()
            keys[key] = {"role": role, "name": name}
        if not keys:
            keys["director-key"] = {"role": "director", "name": "Director"}
        return keys


def get_request_user(request: Request) -> APIUser:
    user = getattr(request.state, "user", None)
    if not isinstance(user, APIUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
