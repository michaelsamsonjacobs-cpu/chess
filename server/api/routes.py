from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from server.database import get_db
from server.models.game import Game, GameImportRequest, GameRead, InvestigationStatus
from server.services.analysis import GameAnalysisPipeline
from server.tasks import enqueue_game_analysis

api_router = APIRouter(tags=["analysis"])


def _game_with_related(session: Session, game_id: int) -> Game:
    stmt = (
        select(Game)
        .where(Game.id == game_id)
        .options(
            selectinload(Game.white_player),
            selectinload(Game.black_player),
            selectinload(Game.investigation),
            selectinload(Game.evaluations),
        )
    )
    result = session.execute(stmt).scalars().first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return result


@api_router.get("/analyses", response_model=List[GameRead])
def list_analyses(
    status_filter: Optional[InvestigationStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> List[GameRead]:
    stmt = (
        select(Game)
        .options(
            selectinload(Game.white_player),
            selectinload(Game.black_player),
            selectinload(Game.investigation),
            selectinload(Game.evaluations),
        )
        .order_by(Game.played_at.desc().nullslast(), Game.id.desc())
    )
    if status_filter:
        stmt = stmt.where(Game.analysis_status == status_filter)
    games = db.execute(stmt).scalars().all()
    return games


@api_router.get("/analyses/{game_id}", response_model=GameRead)
def get_analysis(game_id: int, db: Session = Depends(get_db)) -> GameRead:
    return _game_with_related(db, game_id)


@api_router.post("/games/import", response_model=GameRead, status_code=status.HTTP_202_ACCEPTED)
def import_game(
    request: GameImportRequest,
    db: Session = Depends(get_db),
) -> GameRead:
    pipeline = GameAnalysisPipeline(db)
    game, _ = pipeline.ingest_game(
        request.lichess_id, 
        force=request.force, 
        pgn_text=request.pgn, 
        source=request.source
    )
    db.commit()
    db.refresh(game)
    game = _game_with_related(db, game.id)
    enqueue_game_analysis(game.id, force=request.force)
    return game


@api_router.post("/analyses/{game_id}/requeue", response_model=GameRead)
def requeue_analysis(game_id: int, db: Session = Depends(get_db)) -> GameRead:
    game = _game_with_related(db, game_id)
    game.analysis_status = InvestigationStatus.QUEUED
    if game.investigation:
        game.investigation.status = InvestigationStatus.QUEUED
        game.investigation.summary = None
        game.investigation.details = None
    db.commit()
    enqueue_game_analysis(game.id, force=True)
    return _game_with_related(db, game.id)


@api_router.get("/analyses/{game_id}/moves")
def get_game_moves(game_id: int, db: Session = Depends(get_db)):
    """
    Return detailed move-by-move analysis for visualization.
    
    Each move includes:
    - ply: Move number (half-moves)
    - move_san: Standard algebraic notation (e.g., "e4")
    - accuracy: Move accuracy score (0-1)
    - flagged: Whether this move was flagged as suspicious
    - cp_loss: Centipawn loss for this move
    - best_move: Engine's recommended best move
    - eval_cp: Position evaluation in centipawns
    """
    game = _game_with_related(db, game_id)
    
    if not game.evaluations:
        return {"moves": [], "game_id": game_id, "total_moves": 0}
    
    moves = []
    for eval in sorted(game.evaluations, key=lambda e: e.move_number):
        meta = eval.extra_metadata or {}
        moves.append({
            "ply": eval.move_number,
            "move_san": meta.get("move_san", "?"),
            "move_uci": meta.get("move_uci", ""),
            "player": meta.get("player", "white" if eval.move_number % 2 == 1 else "black"),
            "accuracy": round(eval.accuracy or 0, 3),
            "flagged": eval.flagged,
            "cp_loss": round(meta.get("centipawn_loss", 0), 1),
            "best_move": eval.best_move,
            "eval_cp": round(eval.evaluation_cp, 1),
        })
    
    return {
        "game_id": game_id,
        "lichess_id": game.lichess_id,
        "total_moves": len(moves),
        "white": game.white_player.username,
        "black": game.black_player.username,
        "moves": moves,
    }
