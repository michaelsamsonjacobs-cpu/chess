"""Data acquisition utilities inspired by leading community projects.

The functions in this module encapsulate the API usage patterns observed in
`Avar111ce/Detecting-cheaters-on-lichess`, `bhajji56/cheating-analysis`, and
`RubenLazell/Detecting-Cheating-in-Online-Chess`. They provide a thin, typed
wrapper around common Lichess and Chess.com endpoints so that analysts can pull
consistent, well-structured game samples for downstream processing.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)

LICHESS_GAME_ENDPOINT = "https://lichess.org/api/games/user/{username}"
CHESSCOM_ARCHIVE_ENDPOINT = "https://api.chess.com/pub/player/{username}/games/{year}/{month:02d}"


@dataclass
class GameRecord:
    """Lightweight representation of a game fetched from a public API."""

    platform: str
    player: str
    pgn: str
    raw: Dict[str, Any]


def _ensure_session(session: Optional[requests.Session] = None) -> requests.Session:
    if session is None:
        session = requests.Session()
    return session


def _parse_ndjson(stream: Iterable[bytes]) -> Iterator[Dict[str, Any]]:
    """Yield JSON documents from an NDJSON byte stream."""

    buffer = ""
    for chunk in stream:
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            LOGGER.debug("Skipping undecodable chunk")
            continue
        buffer += text
        lines = buffer.splitlines()
        if buffer and buffer[-1] not in {"\n", "\r"}:
            buffer = lines.pop() if lines else ""
        else:
            buffer = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                LOGGER.debug("Skipping malformed NDJSON line: %s", line[:50])
                continue
    if buffer.strip():
        try:
            yield json.loads(buffer)
        except json.JSONDecodeError:
            LOGGER.debug("Skipping trailing malformed NDJSON line: %s", buffer[:50])


def fetch_lichess_games(
    username: str,
    *,
    max_games: int = 100,
    rated: Optional[bool] = None,
    since: Optional[dt.datetime] = None,
    until: Optional[dt.datetime] = None,
    perf_type: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """Retrieve games from the Lichess API using NDJSON streaming.

    Parameters
    ----------
    username:
        Lichess username to query.
    max_games:
        Maximum number of games to fetch. Mirrors the batching strategy in
        `Avar111ce/Detecting-cheaters-on-lichess`.
    rated:
        Restrict to rated or unrated games.
    since, until:
        Optional time bounds in UTC. When provided they are converted to epoch
        milliseconds as required by the API.
    perf_type:
        Optional performance type (e.g., ``bullet``, ``blitz``).
    additional_params:
        Extra key-value pairs for advanced queries (e.g., ``opening=true``).
    session:
        Optional :class:`requests.Session` to reuse HTTP connections.

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns ``["platform", "player", "pgn", "raw"]``. The
        ``raw`` column contains the parsed JSON payload for downstream feature
        extraction.
    """

    params: Dict[str, Any] = {"max": max_games, "moves": "true", "pgnInJson": "true"}
    if rated is not None:
        params["rated"] = str(rated).lower()
    if since is not None:
        params["since"] = int(since.timestamp() * 1000)
    if until is not None:
        params["until"] = int(until.timestamp() * 1000)
    if perf_type is not None:
        params["perfType"] = perf_type
    if additional_params:
        params.update(additional_params)

    session = _ensure_session(session)
    url = LICHESS_GAME_ENDPOINT.format(username=username)
    headers = {"Accept": "application/x-ndjson"}

    LOGGER.debug("Fetching Lichess games for %s", username)
    response = session.get(url, params=params, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    records: List[GameRecord] = []
    for payload in _parse_ndjson(response.iter_content(chunk_size=8192)):
        pgn = payload.get("pgn", "")
        if not pgn:
            LOGGER.debug("Skipping payload without PGN: %s", payload)
            continue
        records.append(
            GameRecord(platform="lichess", player=username, pgn=pgn, raw=payload)
        )

    LOGGER.info("Fetched %d Lichess games for %s", len(records), username)
    return pd.DataFrame([record.__dict__ for record in records])


def fetch_chesscom_games(
    username: str,
    year: int,
    month: int,
    *,
    session: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """Retrieve games from the Chess.com monthly archive endpoint.

    This mirrors the archival workflow of `RubenLazell/Detecting-Cheating-in-Online-Chess`
    and extends it with per-move clocks inspired by `bhajji56/cheating-analysis`.

    Parameters
    ----------
    username:
        Chess.com username (case-insensitive).
    year, month:
        Archive bucket to download.
    session:
        Optional persistent HTTP session.

    Returns
    -------
    pandas.DataFrame
        DataFrame with the same schema as :func:`fetch_lichess_games`.
    """

    session = _ensure_session(session)
    url = CHESSCOM_ARCHIVE_ENDPOINT.format(username=username.lower(), year=year, month=month)

    LOGGER.debug(
        "Fetching Chess.com archive for %s %04d-%02d", username.lower(), year, month
    )
    response = session.get(url, timeout=30)
    if response.status_code == 404:
        LOGGER.warning("Archive not found for %s %04d-%02d", username, year, month)
        return pd.DataFrame(columns=["platform", "player", "pgn", "raw"])
    response.raise_for_status()

    payload = response.json()
    games: List[GameRecord] = []
    for game in payload.get("games", []):
        pgn = game.get("pgn", "")
        if not pgn:
            continue
        games.append(
            GameRecord(platform="chess.com", player=username, pgn=pgn, raw=game)
        )

    LOGGER.info(
        "Fetched %d Chess.com games for %s from %04d-%02d", len(games), username, year, month
    )
    return pd.DataFrame([game.__dict__ for game in games])


def merge_archives(*frames: pd.DataFrame) -> pd.DataFrame:
    """Concatenate multiple game DataFrames while preserving provenance metadata."""

    if not frames:
        return pd.DataFrame(columns=["platform", "player", "pgn", "raw"])
    normalised = [frame.assign(platform=frame["platform"].str.lower()) for frame in frames]
    return pd.concat(normalised, ignore_index=True)
