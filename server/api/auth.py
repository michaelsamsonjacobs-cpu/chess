
"""
Authentication Routes (Mock OAuth).
"""
from fastapi import APIRouter, Response, status
from fastapi.responses import RedirectResponse
import time
import jwt
from server.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

@router.get("/{provider}/login")
def login_provider(provider: str):
    """Start Mock OAuth flow."""
    # In a real app, we'd redirect to Google/Apple.
    # Here we simulate a successful callback after a short delay URL.
    return RedirectResponse(url=f"/api/auth/callback?provider={provider}")

@router.get("/callback")
def auth_callback(provider: str, response: Response):
    """Mock Callback - logs user in immediately."""
    
    # Create a dummy user token
    # Just reusing ID 1 for simplicity in this demo
    payload = {
        "sub": "1",
        "name": "Demo User",
        "provider": provider,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 7 # 7 days
    }
    
    token = jwt.encode(payload, settings.jwt_secret_key or "secret", algorithm=settings.jwt_algorithm)
    
    # In a real SPA, we might redirect to a frontend route with the token in URL fragment
    # or set a cookie. Let's redirect to root with token in fragment for app.js to pick up.
    return RedirectResponse(url=f"/?token={token}")
