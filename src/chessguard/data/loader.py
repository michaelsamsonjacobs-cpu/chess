"""Data loading helpers for ChessGuard."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List

from .telemetry import SessionTelemetry
from ..utils.pgn import PGNGame, parse_pgn, read_games

__all__ = ["load_pgn_games", "load_single_game", "load_telemetry"]


def load_pgn_games(path: Path | str) -> List[PGNGame]:
    """Load all PGN games from ``path``."""

    return list(read_games(path))


def load_single_game(path: Path | str) -> PGNGame:
    games = load_pgn_games(path)
    if not games:
        raise ValueError(f"No games found in {path}")
    if len(games) > 1:
        raise ValueError(f"Expected a single game in {path}, found {len(games)}")
    return games[0]


def load_telemetry(path: Path | str) -> SessionTelemetry:
    """Load move timing telemetry.

    The function accepts either JSON (list of dicts) or CSV with the
    columns ``move_number``, ``player`` and ``seconds``.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() == ".json":
        records = json.loads(path.read_text(encoding="utf8"))
        if isinstance(records, dict):
            records = records.get("entries", [])
        if not isinstance(records, Iterable):
            raise ValueError("Telemetry JSON must be an array of records")
        return SessionTelemetry.from_iterable(records)  # type: ignore[arg-type]

    with path.open("r", encoding="utf8") as handle:
        reader = csv.DictReader(handle)
        return SessionTelemetry.from_iterable(reader)
