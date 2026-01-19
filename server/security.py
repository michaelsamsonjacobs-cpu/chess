from typing import Any, Dict

import jwt

from .config import get_settings



from datetime import datetime, timedelta

def create_access_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    settings = get_settings()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=1440) # 24 hours default
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

