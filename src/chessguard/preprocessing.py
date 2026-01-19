"""Utilities for cleaning and feature engineering chess games."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

_MOVE_SANITIZE_RE = re.compile(r"[+#?!]")
_MOVE_NUMBER_RE = re.compile(r"^\d+\.{1,3}")
_BLACK_MOVE_PREFIX_RE = re.compile(r"^\.\.\.\s*")


@dataclass(frozen=True)
class RawGame:
    """Representation of the raw payload provided by tournament ingest."""

    moves: Sequence[str]
    result: str


@dataclass(frozen=True)
class PreprocessedGame:
    """Structured representation emitted by :func:`preprocess_game`."""

    normalized_moves: tuple[str, ...]
    move_count: int
    capture_balance: float
    aggression_factor: float
    unique_move_ratio: float
    result: str

    def feature_vector(self) -> dict[str, float]:
        """Return a model-ready feature mapping."""

        return {
            "move_count": float(self.move_count),
            "capture_balance": self.capture_balance,
            "aggression_factor": self.aggression_factor,
            "unique_move_ratio": self.unique_move_ratio,
        }


def _normalize_move(move: str) -> str:
    stripped = move.strip()
    without_numbers = _MOVE_NUMBER_RE.sub("", stripped)
    without_prefix = _BLACK_MOVE_PREFIX_RE.sub("", without_numbers)
    sanitized = _MOVE_SANITIZE_RE.sub("", without_prefix)
    return sanitized.strip().lower()


def _compute_capture_balance(normalized_moves: Sequence[str]) -> float:
    balance = 0.0
    for index, move in enumerate(normalized_moves):
        if "x" not in move:
            continue
        swing = 1.0
        if index % 2 == 0:
            balance += swing
        else:
            balance -= swing
    return balance


def _compute_aggression_factor(normalized_moves: Sequence[str]) -> float:
    if not normalized_moves:
        return 0.0
    captures = sum(1 for move in normalized_moves if "x" in move)
    return captures / len(normalized_moves)


def _compute_unique_move_ratio(normalized_moves: Sequence[str]) -> float:
    if not normalized_moves:
        return 0.0
    unique_moves = len(set(normalized_moves))
    return unique_moves / len(normalized_moves)


def preprocess_game(raw_game: RawGame) -> PreprocessedGame:
    """Convert a :class:`RawGame` payload into engineered features."""

    normalized_moves = tuple(_normalize_move(move) for move in raw_game.moves if move.strip())
    move_count = len(normalized_moves)
    capture_balance = _compute_capture_balance(normalized_moves)
    aggression_factor = _compute_aggression_factor(normalized_moves)
    unique_move_ratio = _compute_unique_move_ratio(normalized_moves)
    return PreprocessedGame(
        normalized_moves=normalized_moves,
        move_count=move_count,
        capture_balance=capture_balance,
        aggression_factor=aggression_factor,
        unique_move_ratio=unique_move_ratio,
        result=raw_game.result,
    )


def preprocess_games(raw_games: Iterable[RawGame]) -> tuple[PreprocessedGame, ...]:
    """Batch convenience wrapper used by the service layer."""

    return tuple(preprocess_game(raw_game) for raw_game in raw_games)


__all__ = [
    "PreprocessedGame",
    "RawGame",
    "preprocess_game",
    "preprocess_games",
]
