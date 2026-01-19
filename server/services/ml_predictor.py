"""
ML-Based Move Prediction Model

Predicts "human-likely" moves based on position features.
Players who consistently play engine moves that humans wouldn't
find will have lower human likelihood scores.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import chess

LOGGER = logging.getLogger(__name__)


@dataclass
class MoveAnalysis:
    """Analysis of a single move's human likelihood."""
    move_uci: str
    move_san: str
    human_likelihood: float  # 0-1, how likely a human would play this
    is_engine_move: bool  # Was this the engine's top choice?
    is_obvious: bool  # Is this move "obvious" (check, capture, recapture)
    complexity_factor: float  # How complex was the position?


@dataclass
class GameHumanScore:
    """Aggregate human likelihood score for a game."""
    total_moves: int
    avg_human_likelihood: float
    non_obvious_engine_moves: int  # Engine moves that weren't obvious
    suspicious_moves: List[MoveAnalysis]
    human_score: float  # 0-100, higher = more human-like


def is_obvious_move(board: chess.Board, move: chess.Move) -> bool:
    """
    Determine if a move is "obvious" - one that any player would consider.
    
    Obvious moves:
    - Only legal move
    - Capturing an undefended piece
    - Check that wins material
    - Recapturing after a trade
    - Escaping a hanging piece
    """
    legal_moves = list(board.legal_moves)
    
    # Only legal move
    if len(legal_moves) == 1:
        return True
    
    # Check
    if board.gives_check(move):
        return True
    
    # Capture
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            # Capturing higher value piece is obvious
            piece_values = {
                chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
            }
            moving_piece = board.piece_at(move.from_square)
            if moving_piece:
                if piece_values.get(captured.piece_type, 0) >= piece_values.get(moving_piece.piece_type, 0):
                    return True
    
    return False


def calculate_position_complexity(board: chess.Board) -> float:
    """
    Calculate position complexity (0-1 scale).
    
    Higher complexity = more candidate moves to consider.
    """
    legal_count = board.legal_moves.count()
    
    # Normalize: 20 moves = 0.5, 40+ moves = 1.0
    complexity = min(1.0, legal_count / 40.0)
    
    # Add tension factor (pieces that can be captured)
    attacks = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            attackers = board.attackers(not piece.color, square)
            if attackers:
                attacks += 1
    
    tension = min(1.0, attacks / 10.0)
    
    return (complexity + tension) / 2


def analyze_move_human_likelihood(
    board: chess.Board,
    move: chess.Move,
    engine_move: Optional[str] = None,
    cp_loss: float = 0.0,
) -> MoveAnalysis:
    """
    Analyze a single move for human likelihood.
    
    Human-like moves:
    - Obvious moves (checks, captures, only legal move)
    - Forward piece development
    - Thematic moves for the opening
    
    Suspicious moves:
    - Deep tactical shots that aren't obvious
    - Quiet moves that require long calculation
    - Defensive moves that are only found by engines
    """
    move_san = board.san(move)
    move_uci = move.uci()
    
    is_obvious = is_obvious_move(board, move)
    complexity = calculate_position_complexity(board)
    is_engine = engine_move and move_uci == engine_move
    
    # Base human likelihood
    if is_obvious:
        # Obvious moves are always human-like
        human_likelihood = 0.95
    elif cp_loss <= 5:
        # Perfect move in complex position is suspicious
        if complexity > 0.7:
            human_likelihood = 0.3
        else:
            human_likelihood = 0.7
    elif cp_loss <= 20:
        # Good move
        human_likelihood = 0.8
    elif cp_loss <= 50:
        # Okay move
        human_likelihood = 0.9
    else:
        # Inaccuracy/mistake is very human
        human_likelihood = 0.95
    
    # Adjust for move type
    if board.is_capture(move):
        human_likelihood = min(1.0, human_likelihood + 0.1)
    
    # Backward moves are less obvious
    from_rank = chess.square_rank(move.from_square)
    to_rank = chess.square_rank(move.to_square)
    is_backward = (board.turn == chess.WHITE and to_rank < from_rank) or \
                  (board.turn == chess.BLACK and to_rank > from_rank)
    
    if is_backward and cp_loss < 10:
        # Backward move that's also strong = suspicious
        human_likelihood *= 0.6
    
    return MoveAnalysis(
        move_uci=move_uci,
        move_san=move_san,
        human_likelihood=human_likelihood,
        is_engine_move=is_engine,
        is_obvious=is_obvious,
        complexity_factor=complexity,
    )


def analyze_game_human_score(
    moves_data: List[Dict],
) -> GameHumanScore:
    """
    Analyze an entire game for human likelihood.
    
    moves_data should be a list of dicts with:
    - fen: Position FEN before the move
    - move_uci: Move played in UCI format
    - engine_move: Engine's top choice (optional)
    - cp_loss: Centipawn loss (optional)
    """
    analyses = []
    suspicious = []
    non_obvious_engine = 0
    
    for move_data in moves_data:
        try:
            board = chess.Board(move_data.get("fen", chess.STARTING_FEN))
            move = chess.Move.from_uci(move_data["move_uci"])
            
            analysis = analyze_move_human_likelihood(
                board=board,
                move=move,
                engine_move=move_data.get("engine_move"),
                cp_loss=move_data.get("cp_loss", 0.0),
            )
            
            analyses.append(analysis)
            
            if analysis.human_likelihood < 0.5:
                suspicious.append(analysis)
            
            if analysis.is_engine_move and not analysis.is_obvious:
                non_obvious_engine += 1
                
        except Exception as e:
            LOGGER.warning(f"Error analyzing move: {e}")
            continue
    
    if not analyses:
        return GameHumanScore(
            total_moves=0,
            avg_human_likelihood=1.0,
            non_obvious_engine_moves=0,
            suspicious_moves=[],
            human_score=100.0,
        )
    
    avg_likelihood = sum(a.human_likelihood for a in analyses) / len(analyses)
    
    # Calculate final human score
    # Penalize for non-obvious engine moves
    engine_penalty = min(0.3, non_obvious_engine * 0.02)
    
    human_score = (avg_likelihood - engine_penalty) * 100
    human_score = max(0, min(100, human_score))
    
    return GameHumanScore(
        total_moves=len(analyses),
        avg_human_likelihood=avg_likelihood,
        non_obvious_engine_moves=non_obvious_engine,
        suspicious_moves=suspicious,
        human_score=human_score,
    )


def get_human_score_for_detection(
    moves_data: List[Dict],
    return_normalized: bool = True,
) -> float:
    """
    Get a normalized human score for use in ensemble detection.
    
    Returns 0-1 where:
    - 1.0 = Definitely human-like
    - 0.0 = Definitely engine-like
    """
    result = analyze_game_human_score(moves_data)
    
    if return_normalized:
        return result.human_score / 100.0
    
    return result.human_score
