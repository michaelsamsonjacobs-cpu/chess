"""Feature extraction helpers.

These functions convert PGNs and engine annotations into structured
DataFrames. They draw on the exploratory workflows published in
`cbarger233/Chess-Game-Analysis` and the time-to-move heuristics from
`bhajji56/cheating-analysis`.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any, Dict, Optional

import chess.pgn

try:  # pragma: no cover - optional dependency
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as _pd


def _require_pandas():
    if pd is None:
        raise ImportError(
            "pandas is required for chessguard.features; install the optional dependency to use this module."
        )
    return pd


def extract_move_features(pgn: str) -> "_pd.DataFrame":
    """Parse a PGN string into a move-level feature table."""

    pd_mod = _require_pandas()
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Unable to parse PGN")

    rows = []
    board = game.board()
    for ply, node in enumerate(game.mainline(), start=1):
        move = node.move
        san = board.san(move)
        clock_td = node.clock()
        clock = clock_td.total_seconds() if clock_td else None
        parent_clock_td = node.parent.clock() if node.parent else None
        parent_clock = parent_clock_td.total_seconds() if parent_clock_td else None
        time_spent = None
        if clock is not None and parent_clock is not None:
            time_spent = max(parent_clock - clock, 0.0)

        pov_eval = node.eval()
        eval_cp: Optional[int]
        if pov_eval is None:
            eval_cp = None
        else:
            try:
                eval_cp = pov_eval.pov(board.turn).score(mate_score=100000)
            except AttributeError:
                eval_cp = None
        rows.append(
            {
                "ply": ply,
                "turn": "white" if board.turn == chess.WHITE else "black",
                "san": san,
                "clock": clock,
                "time_spent": time_spent,
                "comment": node.comment or "",
                "eval_cp": eval_cp,
            }
        )
        board.push(move)

    frame = pd_mod.DataFrame(rows)
    return frame


def attach_engine_evaluations(
    moves: "_pd.DataFrame",
    evaluations: "_pd.DataFrame",
    *,
    join_on: str = "ply",
    suffixes: tuple[str, str] = ("", "_engine"),
) -> "_pd.DataFrame":
    """Merge human move annotations with engine evaluations."""

    _require_pandas()
    return moves.merge(evaluations, on=join_on, how="left", suffixes=suffixes)


def compute_time_pressure_flags(
    moves: "_pd.DataFrame", threshold_seconds: float = 10.0
) -> "_pd.Series":
    """Flag moves completed faster than a given threshold."""

    pd_mod = _require_pandas()
    if "time_spent" not in moves.columns:
        return pd_mod.Series([False] * len(moves), index=moves.index)
    return moves["time_spent"].fillna(float("inf")) <= threshold_seconds


def summarise_move_agreement(moves: "_pd.DataFrame") -> Dict[str, Any]:
    """Calculate aggregate statistics describing engine agreement."""

    _require_pandas()
    summary: Dict[str, Any] = {}
    if "is_engine_move" in moves.columns:
        summary["engine_agreement_rate"] = float(moves["is_engine_move"].mean())
        summary["engine_agreement_count"] = int(moves["is_engine_move"].sum())
    if "centipawn_loss" in moves.columns:
        summary["average_centipawn_loss"] = float(moves["centipawn_loss"].mean())
    if "time_spent" in moves.columns:
        flagged = compute_time_pressure_flags(moves)
        if "is_engine_move" in moves.columns:
            summary["fast_engine_agreement_rate"] = float(
                moves[flagged]["is_engine_move"].mean()
            ) if flagged.any() else 0.0
        summary["fast_move_ratio"] = float(flagged.mean())
    return summary


__all__ = [
    "attach_engine_evaluations",
    "compute_time_pressure_flags",
    "extract_move_features",
    "summarise_move_agreement",
]
