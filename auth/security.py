from datetime import datetime, timedelta
from typing import Any, Dict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from .config import get_settings


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Create a secure hash for the provided password."""
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        password_hasher.verify(hashed_password, password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta is not None else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
