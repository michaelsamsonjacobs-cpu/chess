"""Interactive experiment session manager coordinating engine play."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

import chess
import chess.pgn

from server.services.engine import EngineEvaluation, UCIEngineRunner

from ..schemas.experiment import (
    ExperimentExport,
    ExperimentMoveEvaluation,
    ExperimentMoveLabel,
    ExperimentSession,
    ExperimentSessionMove,
    ExperimentSessionRequest,
    ExperimentSessionState,
)

if TYPE_CHECKING:  # pragma: no cover - used for type checking without runtime import cycles
    from .experiment import ExperimentService


LOGGER = logging.getLogger(__name__)


def _evaluation_to_model(evaluation: EngineEvaluation) -> ExperimentMoveEvaluation:
    """Convert :class:`EngineEvaluation` into a serialisable schema model."""

    return ExperimentMoveEvaluation.from_engine_dict(evaluation.to_dict())


def _compute_centipawn_loss(
    best: EngineEvaluation, played: EngineEvaluation
) -> Optional[int]:
    if best.score_cp is None or played.score_cp is None:
        return None
    return max(0, best.score_cp - played.score_cp)


def _infer_human_label(cpl: Optional[int]) -> str:
    """Derive a qualitative label for a human move from centipawn loss."""

    if cpl is None:
        return "human_move"
    if cpl <= 30:
        return "human_clean"
    if cpl <= 100:
        return "human_inaccuracy"
    if cpl <= 250:
        return "human_mistake"
    return "human_blunder"


def _ensure_move(move_uci: str) -> chess.Move:
    try:
        return chess.Move.from_uci(move_uci)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Invalid UCI move string: {move_uci}") from exc


@dataclass
class _SessionRecord:
    session: ExperimentSession
    board: chess.Board
    player_colour: chess.Color
    history: List[str] = field(default_factory=list)
    moves: List[ExperimentSessionMove] = field(default_factory=list)
    outcome: Optional[str] = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class ExperimentSessionManager:
    """High level orchestrator managing interactive engine-backed sessions."""

    def __init__(
        self,
        experiment_service: "ExperimentService",
        *,
        engine: Optional[UCIEngineRunner] = None,
        analysis_depth: Optional[int] = 14,
        movetime: Optional[int] = None,
    ) -> None:
        self._experiment_service = experiment_service
        self._engine = engine or UCIEngineRunner()
        self._analysis_depth = analysis_depth
        self._movetime = movetime

        self._active: Dict[UUID, _SessionRecord] = {}
        self._archive: Dict[UUID, ExperimentSessionState] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start_session(
        self, request: ExperimentSessionRequest
    ) -> ExperimentSessionState:
        """Begin a new interactive session for a participant."""

        session = self._experiment_service.start_session(request)
        board = self._initialise_board(request.metadata)
        player_colour = self._resolve_player_colour(request.metadata)

        record = _SessionRecord(session=session, board=board, player_colour=player_colour)
        with self._lock:
            self._active[session.session_id] = record

        if board.turn != player_colour and not board.is_game_over():
            LOGGER.debug(
                "Engine to play first move for session %s", session.session_id
            )
            with record.lock:
                self._make_engine_move(record)

        return self._build_state(record)

    def get_state(self, session_id: UUID) -> ExperimentSessionState:
        """Return the current persisted state for a session."""

        with self._lock:
            if session_id in self._active:
                record = self._active[session_id]
                with record.lock:
                    return self._build_state(record)
            if session_id in self._archive:
                return self._archive[session_id]

        raise KeyError(f"Session {session_id} is not active.")

    def apply_player_move(
        self, session_id: UUID, move_uci: str
    ) -> Tuple[ExperimentSessionMove, Optional[ExperimentSessionMove], ExperimentSessionState]:
        """Apply a human move and return resulting state and engine response."""

        record = self._get_active(session_id)
        with record.lock:
            if record.board.turn != record.player_colour:
                raise ValueError("It is not the participant's turn to move.")

            player_move, engine_move = self._handle_player_move(record, move_uci)
            state = self._build_state(record)

        return player_move, engine_move, state

    def finish_session(
        self, session_id: UUID
    ) -> Tuple[ExperimentSessionState, ExperimentExport]:
        """Mark the session as completed and persist the export artefacts."""

        with self._lock:
            archived = self._archive.get(session_id)
        if archived is not None:
            export = self._experiment_service.get_export(session_id)
            return archived, export

        record = self._get_active(session_id)

        with record.lock:
            export = self._build_export(record)
            record.session = record.session.model_copy(update={"status": "completed"})

        persisted = self._experiment_service.complete_session(
            session_id, export.pgn, export.move_labels
        )

        final_state = self._build_state(record)

        with self._lock:
            self._archive[session_id] = final_state
            self._active.pop(session_id, None)

        return final_state, persisted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_active(self, session_id: UUID) -> _SessionRecord:
        with self._lock:
            record = self._active.get(session_id)
        if not record:
            raise KeyError(f"Session {session_id} is not active.")
        return record

    def _initialise_board(self, metadata: Dict[str, str]) -> chess.Board:
        fen = metadata.get("starting_fen") if metadata else None
        if fen:
            try:
                return chess.Board(fen)
            except ValueError as exc:  # pragma: no cover - validated in request normally
                raise ValueError(f"Invalid starting FEN provided: {fen}") from exc
        return chess.Board()

    def _resolve_player_colour(self, metadata: Dict[str, str]) -> chess.Color:
        colour = (metadata or {}).get("player_color", "white").lower()
        return chess.WHITE if colour != "black" else chess.BLACK

    def _handle_player_move(
        self, record: _SessionRecord, move_uci: str
    ) -> Tuple[ExperimentSessionMove, Optional[ExperimentSessionMove]]:
        board = record.board
        move = _ensure_move(move_uci)
        if move not in board.legal_moves:
            raise ValueError(f"Illegal move {move_uci} for the current position.")

        fen_before = board.fen()
        move_san = board.san(move)

        best_eval = self._engine.evaluate_position(
            fen_before,
            depth=self._analysis_depth,
            movetime=self._movetime,
        )
        played_eval = self._engine.evaluate_position(
            fen_before,
            depth=self._analysis_depth,
            movetime=self._movetime,
            search_moves=[move_uci],
        )

        board.push(move)
        record.history.append(move_uci)

        ply = len(record.history)
        centipawn_loss = _compute_centipawn_loss(best_eval, played_eval)
        label = _infer_human_label(centipawn_loss)

        player_move = ExperimentSessionMove(
            ply=ply,
            actor="human",
            move_uci=move_uci,
            move_san=move_san,
            fen_before=fen_before,
            evaluation=_evaluation_to_model(played_eval),
            reference=_evaluation_to_model(best_eval),
            centipawn_loss=centipawn_loss,
            label=label,
        )

        record.moves.append(player_move)

        if board.is_game_over():
            record.outcome = board.result()
            return player_move, None

        engine_move = self._make_engine_move(record)
        return player_move, engine_move

    def _make_engine_move(self, record: _SessionRecord) -> Optional[ExperimentSessionMove]:
        board = record.board
        if board.turn == record.player_colour or board.is_game_over():
            if board.is_game_over():
                record.outcome = board.result()
            return None

        fen_before = board.fen()
        evaluation = self._engine.evaluate_position(
            fen_before,
            depth=self._analysis_depth,
            movetime=self._movetime,
        )
        best_move = evaluation.bestmove
        if not best_move:
            board.push(chess.Move.null())
            record.history.append("0000")
            record.outcome = board.result() if board.is_game_over() else None
            LOGGER.warning("Engine failed to provide bestmove; inserted null move")
            return None

        move = _ensure_move(best_move)
        if move not in board.legal_moves:
            LOGGER.error(
                "Engine suggested illegal move %s; skipping response", best_move
            )
            return None

        move_san = board.san(move)
        board.push(move)
        record.history.append(best_move)

        ply = len(record.history)
        engine_move = ExperimentSessionMove(
            ply=ply,
            actor="engine",
            move_uci=best_move,
            move_san=move_san,
            fen_before=fen_before,
            evaluation=_evaluation_to_model(evaluation),
            reference=None,
            centipawn_loss=None,
            label="engine_move",
        )

        record.moves.append(engine_move)

        if board.is_game_over():
            record.outcome = board.result()

        return engine_move

    def _build_state(self, record: _SessionRecord) -> ExperimentSessionState:
        return ExperimentSessionState(
            session=record.session,
            board_fen=record.board.fen(),
            moves=[move.model_copy(deep=True) for move in record.moves],
            history=list(record.history),
            next_to_move="white" if record.board.turn == chess.WHITE else "black",
            outcome=record.outcome,
        )

    def _build_export(self, record: _SessionRecord) -> ExperimentExport:
        """Generate an :class:`ExperimentExport` for the stored moves."""

        start_board = self._initialise_board(record.session.metadata)
        board = start_board.copy(stack=False)
        game = chess.pgn.Game()

        if start_board.fen() != chess.STARTING_FEN:
            game.setup(start_board.copy(stack=False))
            game.headers["SetUp"] = "1"
            game.headers["FEN"] = start_board.fen()

        game.headers["Event"] = "ChessGuard Experiment"
        game.headers["Site"] = "ChessGuard Engine Portal"
        game.headers["White"] = (
            record.session.player_id if record.player_colour == chess.WHITE else "ChessGuard Engine"
        )
        game.headers["Black"] = (
            "ChessGuard Engine" if record.player_colour == chess.WHITE else record.session.player_id
        )
        game.headers.setdefault("Result", "*")

        node = game
        for move_uci in record.history:
            move = _ensure_move(move_uci)
            node = node.add_variation(move)
            board.push(move)

        result = record.outcome or (board.result() if board.is_game_over() else "*")
        game.headers["Result"] = result

        pgn = str(game)
        move_labels = list(self._generate_labels(record.moves))

        return ExperimentExport(
            session_id=record.session.session_id, pgn=pgn, move_labels=move_labels
        )

    def _generate_labels(
        self, moves: Iterable[ExperimentSessionMove]
    ) -> Iterable[ExperimentMoveLabel]:
        for move in moves:
            notes = None
            if move.centipawn_loss is not None:
                notes = f"centipawn_loss={move.centipawn_loss}"
            yield ExperimentMoveLabel(
                ply=move.ply,
                label=move.label,
                confidence=0.85 if move.actor == "human" else 1.0,
                notes=notes,
            )

