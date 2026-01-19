"""Utilities for replaying historical tournaments against the current engine."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from chessguard import ChessGuardEngine, RawGame, preprocess_game


@dataclass(frozen=True)
class HistoricalGame:
    game_id: str
    moves: Sequence[str]
    result: str
    label: bool


@dataclass(frozen=True)
class ReplayResult:
    game_id: str
    probability: float
    alert: bool
    label: bool


def load_historical_dataset(path: Path) -> list[HistoricalGame]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    games: list[HistoricalGame] = []
    for entry in payload:
        games.append(
            HistoricalGame(
                game_id=entry["game_id"],
                moves=entry["moves"],
                result=entry["result"],
                label=bool(entry["label"]),
            )
        )
    return games


def replay_tournament(
    engine: ChessGuardEngine, games: Iterable[HistoricalGame]
) -> list[ReplayResult]:
    results: list[ReplayResult] = []
    for game in games:
        preprocessed = preprocess_game(RawGame(moves=game.moves, result=game.result))
        evaluation = engine.evaluate(preprocessed)
        results.append(
            ReplayResult(
                game_id=game.game_id,
                probability=evaluation.probability,
                alert=evaluation.alert,
                label=game.label,
            )
        )
    return results


__all__ = ["HistoricalGame", "ReplayResult", "load_historical_dataset", "replay_tournament"]
