"""FastAPI application for the ChessGuard backend (merged).

- Includes database init and core API/UI routers.
- Adds Lichess integration routes and graceful shutdown.
- Serves a static frontend if present.
- Provides a CLI entrypoint (`python -m server.main`) with optional TLS.
"""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import api_router
from .api.ui import ui_router
from .app import router as legacy_router
from .config import get_settings
from .database import Base, engine
from .dependencies import lichess_service
from .routes import lichess

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(title="ChessGuard", version="0.1.0")

    # Ensure tables exist (SQLite/dev convenience; for prod use migrations)
    # Import all models here so they are registered with Base.metadata
    from .models.banned_player import BannedPlayer
    from .agents.models import ConnectedAccount, SyncJob, CheatReport
    from .models.game import Game, BatchAnalysis  # Ensure core game models are imported
    
    Base.metadata.create_all(bind=engine)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Core routers
    app.include_router(api_router, prefix="/api")
    app.include_router(ui_router)
    
    # Authentication API
    from .api.auth import router as auth_router
    app.include_router(auth_router)

    # Lichess integration API
    app.include_router(lichess.router)
    
    # Chess.com Audit API
    from .api import chesscom
    app.include_router(chesscom.router)
    
    # Lichess Audit API (Detective Mode)
    from .api import lichess_audit
    app.include_router(lichess_audit.router)
    
    # Batch Analysis API
    from .api.batch import batch_router
    app.include_router(batch_router)
    
    # Player History API
    from .api.history_routes import history_router
    app.include_router(history_router)
    
    # Known Cheater Database API
    from .api.cheater_routes import cheater_router
    app.include_router(cheater_router)
    
    # PDF Reporting API
    from .api.reporting_routes import reporting_router
    app.include_router(reporting_router)

    # Automated Agent API
    from .api.agent_routes import router as agent_router
    app.include_router(agent_router, prefix="/api")
    
    # Stripe Payment API
    from .api.stripe_routes import router as stripe_router
    app.include_router(stripe_router)

    # Legacy game/profile endpoints
    app.include_router(legacy_router)

    # Static frontend (if present)
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    assets_dir = frontend_dir / "assets"
    
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    # Start background scheduler
    @app.on_event("startup")
    async def _startup() -> None:
        from .scheduler import start_scheduler
        start_scheduler()

    # Graceful shutdown for shared clients/services
    @app.on_event("shutdown")
    async def _shutdown() -> None:
        from .scheduler import stop_scheduler
        stop_scheduler()
        await lichess_service.aclose()

    return app


app = create_app()


def main() -> None:
    """CLI entrypoint with optional TLS support via environment/config."""
    settings = get_settings()
    kwargs = {"host": "0.0.0.0", "port": 8000}
    if getattr(settings, "tls_cert_path", None) and getattr(settings, "tls_key_path", None):
        kwargs.update(
            {"ssl_certfile": settings.tls_cert_path, "ssl_keyfile": settings.tls_key_path}
        )
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":
    main()

