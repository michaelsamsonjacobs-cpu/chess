"""Service container wiring for the ChessGuard backend."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..repositories import AppRepositories
from .dataset import DatasetService
from .experiment import ExperimentService
from .experiment_session import ExperimentSessionManager
from .game_analysis import GameService
from .moderation import ModerationService
from .profile_analysis import ProfileService
from .public import PublicAnalysisService


@dataclass
class ServiceContainer:
    """Aggregated service layer used for dependency injection within FastAPI."""

    repositories: AppRepositories
    games: GameService = field(init=False)
    profiles: ProfileService = field(init=False)
    experiments: ExperimentService = field(init=False)
    experiment_sessions: ExperimentSessionManager = field(init=False)
    datasets: DatasetService = field(init=False)
    moderation: ModerationService = field(init=False)
    public: PublicAnalysisService = field(init=False)

    def __post_init__(self) -> None:
        self.games = GameService(self.repositories)
        self.profiles = ProfileService(self.repositories)
        self.experiments = ExperimentService(self.repositories)
        self.experiment_sessions = ExperimentSessionManager(self.experiments)
        self.datasets = DatasetService(self.repositories)
        self.moderation = ModerationService(self.repositories)
        self.public = PublicAnalysisService()


__all__ = [
    "DatasetService",
    "ExperimentService",
    "GameService",
    "ModerationService",
    "ProfileService",
    "PublicAnalysisService",
    "ServiceContainer",
]

