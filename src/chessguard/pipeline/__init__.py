"""High-level orchestration for ChessGuard analyses."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import chess
import chess.pgn

from ..config import PipelineConfig
from ..engine import Engine, MoveInput

GameInput = Union[str, Path, Sequence[MoveInput], chess.pgn.Game]
"""Accepted input types for :class:`AnalysisPipeline`."""


class AnalysisPipeline:
    """Coordinate preprocessing, inference, and postprocessing."""

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        engine: Optional[Engine] = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.engine = engine or Engine(self.config.engine)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def run(self, source: GameInput, metadata: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Execute the full pipeline on the provided input."""

        board, moves, extracted_metadata = self.preprocess(source)
        combined_metadata: Dict[str, Any] = {}
        combined_metadata.update(self.config.extra_metadata)
        combined_metadata.update(extracted_metadata)
        if metadata:
            combined_metadata.update(metadata)

        result = self.inference(board, moves, combined_metadata)
        return self.postprocess(result)

    def preprocess(self, source: GameInput) -> Tuple[chess.Board, List[MoveInput], Dict[str, Any]]:
        """Convert raw PGN strings or move sequences into structured inputs."""

        if isinstance(source, chess.pgn.Game):
            return self._preprocess_game(source, source_token="object")

        if isinstance(source, Path):
            text = source.read_text(encoding="utf-8")
            game = chess.pgn.read_game(io.StringIO(text))
            if game is None:
                return chess.Board(), self._normalise_move_list(text.split()), {"source_path": str(source)}
            board, moves, metadata = self._preprocess_game(game, source_token=str(source))
            metadata["source_path"] = str(source)
            return board, moves, metadata

        if isinstance(source, str):
            text = source.strip()
            if not text:
                return chess.Board(), [], {}
            game = chess.pgn.read_game(io.StringIO(text))
            if game is not None:
                return self._preprocess_game(game, source_token="inline")
            return chess.Board(), self._normalise_move_list(text.split()), {}

        if isinstance(source, Sequence):
            return chess.Board(), self._normalise_move_list(source), {}

        raise TypeError(f"Unsupported pipeline input type: {type(source)!r}")

    def inference(
        self,
        board: chess.Board,
        moves: Sequence[MoveInput],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Delegate to the engine for scoring."""

        return self.engine.analyze(moves, board=board, metadata=metadata)

    def postprocess(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Augment engine output with convenience summaries."""

        if not self.config.postprocess:
            return result

        enriched = dict(result)
        moves = enriched.get("moves", [])
        suspicious_moves = [move for move in moves if move.get("is_suspicious")]
        enriched["summary"] = {
            "total_moves": len(moves),
            "suspicious_moves": len(suspicious_moves),
            "top_suspicious": suspicious_moves[:5],
        }
        return enriched

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _preprocess_game(self, game: chess.pgn.Game, source_token: str) -> Tuple[chess.Board, List[MoveInput], Dict[str, Any]]:
        headers = dict(game.headers)
        if not self.config.allow_incomplete_games and headers.get("Result") == "*":
            raise ValueError("Incomplete game encountered; enable 'allow_incomplete_games' to override.")

        initial_board = self._initial_board_from_headers(headers)
        moves = list(game.mainline_moves())
        metadata: Dict[str, Any] = {
            "event": headers.get("Event"),
            "site": headers.get("Site"),
            "date": headers.get("Date"),
            "round": headers.get("Round"),
            "white": headers.get("White"),
            "black": headers.get("Black"),
            "result": headers.get("Result"),
            "source": source_token,
        }
        metadata = {key: value for key, value in metadata.items() if value}
        return initial_board, moves, metadata

    def _normalise_move_list(self, moves: Sequence[MoveInput]) -> List[MoveInput]:
        normalised: List[MoveInput] = []
        for token in moves:
            if isinstance(token, chess.Move):
                normalised.append(token)
                continue
            if not isinstance(token, str):
                raise TypeError(f"Unsupported move token {token!r}")
            cleaned = token.strip()
            if not cleaned:
                continue
            if cleaned in {"1-0", "0-1", "1/2-1/2", "*"}:
                continue
            if cleaned.endswith(".") or cleaned.replace(".", "").isdigit():
                continue
            if cleaned[0].isdigit() and "." in cleaned:
                _, suffix = cleaned.split(".", 1)
                cleaned = suffix
                if not cleaned:
                    continue
            if cleaned.startswith("..."):
                cleaned = cleaned.lstrip(".")
                if not cleaned:
                    continue
            normalised.append(cleaned)
        return normalised

    def _initial_board_from_headers(self, headers: Mapping[str, Any]) -> chess.Board:
        if headers.get("SetUp") == "1" and headers.get("FEN"):
            try:
                return chess.Board(headers["FEN"])
            except ValueError as exc:
                raise ValueError(f"Invalid FEN in PGN headers: {headers['FEN']!r}") from exc
        return chess.Board()


__all__ = ["AnalysisPipeline", "GameInput"]
