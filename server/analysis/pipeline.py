"""Analysis helpers that combine PGN parsing with engine evaluations."""
from __future__ import annotations

import datetime as dt
import io
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

try:
    import chess
    import chess.pgn
except ImportError as exc:  # pragma: no cover - imported lazily for environments without deps
    raise ImportError(
        "The analysis pipeline requires the 'python-chess' package. "
        "Install it with `pip install python-chess`."
    ) from exc

from server.services.engine import EngineEvaluation, UCIEngineRunner

__all__ = [
    "MoveAnalysis",
    "GameAnalysisSummary",
    "GameAnalysisResult",
    "GameAnalysisPipeline",
]


@dataclass
class MoveAnalysis:
    """Container for information gathered when analysing a single move."""

    ply: int
    move_number: int
    player: str
    move_san: str
    move_uci: str
    fen_before: str
    best: EngineEvaluation
    played: EngineEvaluation
    centipawn_loss: Optional[int]

    def to_dict(self) -> Dict[str, object]:
        return {
            "ply": self.ply,
            "move_number": self.move_number,
            "player": self.player,
            "move_san": self.move_san,
            "move_uci": self.move_uci,
            "fen_before": self.fen_before,
            "best": self.best.to_dict(),
            "played": self.played.to_dict(),
            "centipawn_loss": self.centipawn_loss,
        }


@dataclass
class GameAnalysisSummary:
    """Aggregate metrics computed over a full game analysis."""

    game_id: Optional[str]
    moves_analyzed: int
    average_centipawn_loss: Dict[str, Optional[float]]
    maximum_centipawn_loss: Dict[str, Optional[int]]

    generated_at: str = field(
        default_factory=lambda: dt.datetime.utcnow().replace(microsecond=0).isoformat()
    )

    def to_dict(self) -> Dict[str, object]:
        return {
            "game_id": self.game_id,
            "moves_analyzed": self.moves_analyzed,
            "average_centipawn_loss": self.average_centipawn_loss,
            "maximum_centipawn_loss": self.maximum_centipawn_loss,
            "generated_at": self.generated_at,
        }


@dataclass
class GameAnalysisResult:
    """Full artefact returned by :class:`GameAnalysisPipeline`."""

    summary: GameAnalysisSummary
    moves: List[MoveAnalysis]

    def to_dict(self) -> Dict[str, object]:
        return {
            "summary": self.summary.to_dict(),
            "moves": [move.to_dict() for move in self.moves],
        }


class GameAnalysisPipeline:
    """Run Stockfish assisted analysis over PGN games."""

    def __init__(
        self,
        engine: UCIEngineRunner,
        *,
        depth: Optional[int] = 16,
        movetime: Optional[int] = None,
    ) -> None:
        if depth is not None and depth <= 0:
            raise ValueError("Depth must be positive or None.")

        self.engine = engine
        self.depth = depth
        self.movetime = movetime

    def analyse_game(self, game: chess.pgn.Game, game_id: Optional[str] = None) -> GameAnalysisResult:
        """Analyse a :mod:`python-chess` game instance."""

        board = game.board()
        moves: List[MoveAnalysis] = []

        for ply_index, move in enumerate(game.mainline_moves(), start=1):
            fen_before = board.fen()
            move_number = board.fullmove_number
            player = "white" if board.turn == chess.WHITE else "black"
            move_san = board.san(move)
            move_uci = move.uci()

            best_eval = self.engine.evaluate_position(
                fen_before,
                depth=self.depth,
                movetime=self.movetime,
                multipv=2,
            )
            played_eval = self.engine.evaluate_position(
                fen_before,
                depth=self.depth,
                movetime=self.movetime,
                search_moves=[move_uci],
            )

            centipawn_loss = self._compute_centipawn_loss(best_eval, played_eval)

            moves.append(
                MoveAnalysis(
                    ply=ply_index,
                    move_number=move_number,
                    player=player,
                    move_san=move_san,
                    move_uci=move_uci,
                    fen_before=fen_before,
                    best=best_eval,
                    played=played_eval,
                    centipawn_loss=centipawn_loss,
                )
            )

            board.push(move)

        summary = self._summarise(moves, game_id or game.headers.get("Event"))
        return GameAnalysisResult(summary=summary, moves=moves)

    def analyse_pgn(self, pgn: str, game_id: Optional[str] = None) -> GameAnalysisResult:
        """Parse a PGN string and analyse the first game contained within."""

        pgn_io = io.StringIO(pgn)
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            raise ValueError("No game could be parsed from PGN input.")
        return self.analyse_game(game, game_id=game_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _compute_centipawn_loss(
        self, best: EngineEvaluation, played: EngineEvaluation
    ) -> Optional[int]:
        if best.score_cp is None or played.score_cp is None:
            return None
        diff = best.score_cp - played.score_cp
        return max(0, diff)

    def _summarise(
        self, moves: Sequence[MoveAnalysis], game_id: Optional[str]
    ) -> GameAnalysisSummary:
        white_losses: List[int] = []
        black_losses: List[int] = []

        for move in moves:
            if move.centipawn_loss is None:
                continue
            if move.player == "white":
                white_losses.append(move.centipawn_loss)
            else:
                black_losses.append(move.centipawn_loss)

        averages = {
            "white": statistics.fmean(white_losses) if white_losses else None,
            "black": statistics.fmean(black_losses) if black_losses else None,
        }
        maxima = {
            "white": max(white_losses) if white_losses else None,
            "black": max(black_losses) if black_losses else None,
        }

        return GameAnalysisSummary(
            game_id=game_id,
            moves_analyzed=len(moves),
            average_centipawn_loss=averages,
            maximum_centipawn_loss=maxima,
        )
