"""Engine-backed analysis primitives.

This module integrates Stockfish-style evaluations into the data pipeline,
borrowing heuristics from community projects that compare human move choices to
engine recommendations under time pressure.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import pandas as pd
import chess
import chess.engine
import chess.pgn

DEFAULT_DEPTH = 15
DEFAULT_MOVETIME = 0.2


@dataclass
class GameSummary:
    """Aggregate statistics describing a single analysed game."""

    total_moves: int
    average_centipawn_loss: float
    median_centipawn_loss: float
    engine_agreement_rate: float
    max_engine_streak: int
    fast_engine_agreement_rate: Optional[float] = None
    fast_move_ratio: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        """Return a serialisable dictionary representation."""

        data: Dict[str, float] = {
            "total_moves": float(self.total_moves),
            "average_centipawn_loss": self.average_centipawn_loss,
            "median_centipawn_loss": self.median_centipawn_loss,
            "engine_agreement_rate": self.engine_agreement_rate,
            "max_engine_streak": float(self.max_engine_streak),
        }
        if self.fast_engine_agreement_rate is not None:
            data["fast_engine_agreement_rate"] = self.fast_engine_agreement_rate
        if self.fast_move_ratio is not None:
            data["fast_move_ratio"] = self.fast_move_ratio
        return data


def _score_to_centipawns(score: Optional[chess.engine.PovScore], pov: chess.Color) -> Optional[float]:
    if score is None:
        return None
    try:
        return float(score.pov(pov).score(mate_score=100000))
    except AttributeError:
        return None


def _build_limit(
    limit: Optional[chess.engine.Limit] = None,
    *,
    depth: Optional[int] = None,
    movetime: Optional[float] = None,
) -> chess.engine.Limit:
    if limit is not None:
        return limit
    if depth is not None:
        return chess.engine.Limit(depth=depth)
    if movetime is not None:
        return chess.engine.Limit(time=movetime)
    return chess.engine.Limit(depth=DEFAULT_DEPTH, time=DEFAULT_MOVETIME)


def evaluate_game(
    pgn: str,
    *,
    engine_path: str,
    limit: Optional[chess.engine.Limit] = None,
    depth: Optional[int] = None,
    movetime: Optional[float] = None,
    multipv: int = 1,
) -> pd.DataFrame:
    """Run engine analysis on a PGN game.

    Parameters
    ----------
    pgn:
        Full PGN text including headers and movetext.
    engine_path:
        Filesystem path to a UCI-compatible engine (e.g., Stockfish).
    limit, depth, movetime:
        Analysis budget. When ``limit`` is not supplied, ``depth`` or ``movetime``
        can be used to configure the engine limit directly.
    multipv:
        Number of principal variations to request from the engine.

    Returns
    -------
    pandas.DataFrame
        Per-ply analysis with centipawn loss, engine agreement, and engine
        metadata (depth, nodes, nps).
    """

    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Unable to parse PGN")

    board = game.board()
    rows: List[Dict[str, Optional[float]]] = []
    limit_obj = _build_limit(limit, depth=depth, movetime=movetime)

    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        for ply, move in enumerate(game.mainline_moves(), start=1):
            color_to_move = board.turn
            san = board.san(move)
            info = engine.analyse(board, limit_obj, multipv=multipv)
            infos: Iterable[chess.engine.InfoDict]
            if isinstance(info, list):
                infos = info
            else:
                infos = [info]
            primary_info = next(iter(infos))
            best_pv = primary_info.get("pv", [])
            best_move = best_pv[0] if best_pv else None
            best_san = board.san(best_move) if best_move else None
            best_score_cp = _score_to_centipawns(primary_info.get("score"), color_to_move)

            board.push(move)
            reply_info = engine.analyse(board, limit_obj)
            actual_score_cp = _score_to_centipawns(reply_info.get("score"), not board.turn)
            centipawn_loss = None
            if best_score_cp is not None and actual_score_cp is not None:
                centipawn_loss = max(best_score_cp - actual_score_cp, 0.0)

            rows.append(
                {
                    "ply": ply,
                    "turn": "white" if color_to_move == chess.WHITE else "black",
                    "move_uci": move.uci(),
                    "move_san": san,
                    "best_move_uci": best_move.uci() if best_move else None,
                    "best_move_san": best_san,
                    "best_score_cp": best_score_cp,
                    "actual_score_cp": actual_score_cp,
                    "centipawn_loss": centipawn_loss,
                    "is_engine_move": best_move == move if best_move else False,
                    "engine_depth": primary_info.get("depth"),
                    "engine_seldepth": primary_info.get("seldepth"),
                    "engine_nodes": primary_info.get("nodes"),
                    "engine_nps": primary_info.get("nps"),
                }
            )

    return pd.DataFrame(rows)


def _max_streak(flags: Iterable[bool]) -> int:
    best = 0
    current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def summarise_game(evaluations: pd.DataFrame) -> GameSummary:
    """Aggregate per-move engine evaluations into summary statistics."""

    if evaluations.empty:
        raise ValueError("Evaluation DataFrame is empty")

    total_moves = len(evaluations)
    acpl = float(evaluations["centipawn_loss"].mean())
    median_cpl = float(evaluations["centipawn_loss"].median())
    engine_agreement = float(evaluations["is_engine_move"].mean())
    streak = _max_streak(evaluations["is_engine_move"].astype(bool))

    fast_agreement: Optional[float] = None
    fast_move_ratio: Optional[float] = None
    if "time_spent" in evaluations.columns:
        fast_moves = evaluations["time_spent"].fillna(float("inf")) <= 10.0
        fast_move_ratio = float(fast_moves.mean())
        if fast_moves.any():
            fast_agreement = float(evaluations.loc[fast_moves, "is_engine_move"].mean())
        else:
            fast_agreement = 0.0

    return GameSummary(
        total_moves=total_moves,
        average_centipawn_loss=acpl,
        median_centipawn_loss=median_cpl,
        engine_agreement_rate=engine_agreement,
        max_engine_streak=streak,
        fast_engine_agreement_rate=fast_agreement,
        fast_move_ratio=fast_move_ratio,
    )
