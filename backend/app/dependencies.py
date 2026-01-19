"""FastAPI dependency helpers for accessing repositories and services."""

from __future__ import annotations

from fastapi import Depends, Request

from .repositories import AppRepositories
from .services import (
    DatasetService,
    ExperimentService,
    GameService,
    ModerationService,
    ProfileService,
    ServiceContainer,
)
from .services.experiment_session import ExperimentSessionManager
from .services.public import PublicAnalysisService


def get_repositories(request: Request) -> AppRepositories:
    return request.app.state.repositories


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


def get_game_service(services: ServiceContainer = Depends(get_services)) -> GameService:
    return services.games


def get_profile_service(services: ServiceContainer = Depends(get_services)) -> ProfileService:
    return services.profiles


def get_experiment_service(services: ServiceContainer = Depends(get_services)) -> ExperimentService:
    return services.experiments


def get_experiment_session_manager(
    services: ServiceContainer = Depends(get_services),
) -> ExperimentSessionManager:
    return services.experiment_sessions


def get_dataset_service(services: ServiceContainer = Depends(get_services)) -> DatasetService:
    return services.datasets


def get_moderation_service(services: ServiceContainer = Depends(get_services)) -> ModerationService:
    return services.moderation


def get_public_service(services: ServiceContainer = Depends(get_services)) -> PublicAnalysisService:
    return services.public

