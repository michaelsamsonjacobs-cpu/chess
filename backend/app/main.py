"""Entry point for the ChessGuard FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import analyze, datasets, experiment, experiment_play, games, moderation, profiles
from .repositories import AppRepositories
from .services import ServiceContainer

app = FastAPI(
    title="ChessGuard",
    description="Anti-cheat intelligence platform combining engine and psychological analytics.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

repositories = AppRepositories()
services = ServiceContainer(repositories=repositories)
app.state.repositories = repositories
app.state.services = services

app.include_router(games.router)
app.include_router(profiles.router)
app.include_router(experiment.router)
app.include_router(experiment_play.router)
app.include_router(datasets.router)
app.include_router(moderation.router)
app.include_router(analyze.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Basic health endpoint returning platform context."""

    return {
        "name": "ChessGuard",
        "version": app.version,
        "description": "API-first anti-cheat intelligence platform",
    }

