"""Utilities for working with PGN (Portable Game Notation) files.

This module intentionally implements a lean subset of the PGN standard
so that we can parse games without external dependencies.  It is capable
of reading basic headers, a single main line of moves and the standard
termination markers.  Comments (``{...}`` or ``;``) and parenthesised
variations are stripped before tokenisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, Iterator, List, Optional

__all__ = ["MoveRecord", "PGNGame", "parse_pgn", "read_games"]

TAG_PATTERN = re.compile(r"\[(?P<key>[A-Za-z0-9_]+)\s+\"(?P<value>[^\"]*)\"\]")
COMMENT_PATTERN = re.compile(r"\{[^}]*\}|;[^\n]*")


@dataclass(frozen=True)
class MoveRecord:
    """Represents a single pair of moves in a PGN game."""

    move_number: int
    white: Optional[str]
    black: Optional[str]


@dataclass(frozen=True)
class PGNGame:
    """Container for a parsed PGN game."""

    tags: Dict[str, str]
    moves: List[MoveRecord]
    result: str

    @property
    def white_player(self) -> str:
        return self.tags.get("White", "Unknown")

    @property
    def black_player(self) -> str:
        return self.tags.get("Black", "Unknown")

    @property
    def event(self) -> str:
        return self.tags.get("Event", "")

    def total_moves(self) -> int:
        total = 0
        for move in self.moves:
            if move.white:
                total += 1
            if move.black:
                total += 1
        return total


def _strip_comments(move_section: str) -> str:
    without_block = COMMENT_PATTERN.sub(" ", move_section)
    without_variations = re.sub(r"\\([^)]*\\)", " ", without_block)
    return without_variations


def _tokenise(move_section: str) -> Iterator[str]:
    clean_section = _strip_comments(move_section)
    for token in clean_section.replace("\n", " ").split():
        token = token.strip()
        if token:
            yield token


_RESULT_MARKERS = {"1-0", "0-1", "1/2-1/2", "*"}


def parse_pgn(text: str) -> PGNGame:
    tags: Dict[str, str] = {}
    moves: List[MoveRecord] = []

    header_lines: List[str] = []
    move_lines: List[str] = []
    lines = text.strip().splitlines()
    in_header = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and in_header:
            header_lines.append(stripped)
        else:
            in_header = False
            move_lines.append(stripped)

    for line in header_lines:
        match = TAG_PATTERN.match(line)
        if match:
            tags[match.group("key")] = match.group("value")

    tokens = list(_tokenise(" ".join(move_lines)))
    moves, result = _consume_moves(tokens)
    return PGNGame(tags=tags, moves=moves, result=result or tags.get("Result", "*"))


def _consume_moves(tokens: List[str]) -> tuple[List[MoveRecord], Optional[str]]:
    moves: List[MoveRecord] = []
    current_move_number = 1
    ply_is_white = True
    result: Optional[str] = None

    for token in tokens:
        if token in _RESULT_MARKERS:
            result = token
            break

        if token.endswith("."):
            digits = re.sub(r"[^0-9]", "", token)
            if digits:
                current_move_number = int(digits)
                ply_is_white = not token.endswith("...")
            else:
                ply_is_white = token.endswith("...")
            continue

        if ply_is_white:
            moves.append(MoveRecord(move_number=current_move_number, white=token, black=None))
            ply_is_white = False
        else:
            if not moves:
                moves.append(MoveRecord(move_number=current_move_number, white=None, black=token))
            else:
                last = moves[-1]
                if last.move_number == current_move_number and last.black is None:
                    moves[-1] = MoveRecord(move_number=last.move_number, white=last.white, black=token)
                else:
                    moves.append(MoveRecord(move_number=current_move_number, white=None, black=token))
            current_move_number += 1
            ply_is_white = True

    return moves, result


def read_games(path: Path | str) -> Iterable[PGNGame]:
    text = Path(path).read_text(encoding="utf8")
    buffer: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if buffer and _contains_result(buffer):
                yield parse_pgn("\n".join(buffer))
                buffer = []
            continue
        buffer.append(line)
        if _contains_result(buffer):
            yield parse_pgn("\n".join(buffer))
            buffer = []
    if buffer:
        yield parse_pgn("\n".join(buffer))


def _contains_result(lines: List[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            continue
        for marker in _RESULT_MARKERS:
            if marker in stripped:
                return True
    return False
