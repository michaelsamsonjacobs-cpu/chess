"""Position Complexity Analysis.

Calculates complexity metrics for chess positions to:
1. Provide context for accuracy evaluation
2. Enable time-complexity correlation analysis
3. Identify positions where high accuracy is more/less expected

Key insight:
- High accuracy in SIMPLE positions is expected for all players
- High accuracy in COMPLEX positions is more suspicious for lower-rated players
- Humans tend to struggle with high-complexity positions under time pressure

Complexity factors:
1. Legal moves count - more options = more complex
2. Tension (attacked pieces) - pieces under attack = tactical complexity
3. Material imbalance - unusual material = harder to evaluate
4. Piece mobility - restricted pieces = positional complexity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import chess

LOGGER = logging.getLogger(__name__)


@dataclass
class PositionComplexity:
    """Complexity metrics for a single position."""
    legal_moves_count: int  # Number of legal moves available
    captures_available: int  # Number of captures possible
    checks_available: int  # Number of checking moves
    pieces_attacked: int  # Number of pieces under attack
    pieces_defending: int  # Number of pieces defended
    material_imbalance: int  # Deviation from equal material (centipawns)
    piece_mobility: float  # Average mobility per piece (0-1)
    complexity_score: float  # Normalized composite score (0-1)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "legal_moves_count": self.legal_moves_count,
            "captures_available": self.captures_available,
            "checks_available": self.checks_available,
            "pieces_attacked": self.pieces_attacked,
            "pieces_defending": self.pieces_defending,
            "material_imbalance": self.material_imbalance,
            "piece_mobility": round(self.piece_mobility, 3),
            "complexity_score": round(self.complexity_score, 3),
        }


# Piece values for material calculation
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def count_material(board: chess.Board, color: chess.Color) -> int:
    """Count total material for a color in centipawns."""
    total = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        count = len(board.pieces(piece_type, color))
        total += count * PIECE_VALUES[piece_type]
    return total


def count_attacked_pieces(board: chess.Board, color: chess.Color) -> int:
    """Count pieces of 'color' that are attacked by opponent."""
    attacked = 0
    opponent = not color
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            if board.is_attacked_by(opponent, square):
                attacked += 1
    
    return attacked


def count_defended_pieces(board: chess.Board, color: chess.Color) -> int:
    """Count pieces of 'color' that are defended by own pieces."""
    defended = 0
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            if board.is_attacked_by(color, square):
                defended += 1
    
    return defended


def calculate_piece_mobility(board: chess.Board, color: chess.Color) -> float:
    """
    Calculate average mobility per piece.
    
    Returns 0-1 where 1 = maximum mobility for all pieces.
    """
    # Temporarily switch to the color's turn to count moves
    original_turn = board.turn
    board.turn = color
    
    total_moves = len(list(board.legal_moves))
    
    # Count pieces (excluding king, which always has moves)
    piece_count = len(board.pieces(chess.PAWN, color)) + \
                  len(board.pieces(chess.KNIGHT, color)) + \
                  len(board.pieces(chess.BISHOP, color)) + \
                  len(board.pieces(chess.ROOK, color)) + \
                  len(board.pieces(chess.QUEEN, color))
    
    board.turn = original_turn
    
    if piece_count == 0:
        return 0.0
    
    # Average moves per piece, normalized (assume max ~7 moves per piece average)
    avg_moves = total_moves / piece_count
    return min(1.0, avg_moves / 7.0)


def analyze_position_complexity(board: chess.Board) -> PositionComplexity:
    """
    Analyze complexity of a chess position.
    
    Returns PositionComplexity object with various metrics.
    """
    # Legal moves
    legal_moves = list(board.legal_moves)
    legal_moves_count = len(legal_moves)
    
    # Captures and checks
    captures = [m for m in legal_moves if board.is_capture(m)]
    captures_count = len(captures)
    
    checks = []
    for move in legal_moves:
        board.push(move)
        if board.is_check():
            checks.append(move)
        board.pop()
    checks_count = len(checks)
    
    # Attacked and defended pieces
    current_color = board.turn
    pieces_attacked = count_attacked_pieces(board, current_color)
    pieces_defending = count_defended_pieces(board, current_color)
    
    # Material imbalance
    white_material = count_material(board, chess.WHITE)
    black_material = count_material(board, chess.BLACK)
    material_imbalance = abs(white_material - black_material)
    
    # Piece mobility
    mobility = calculate_piece_mobility(board, current_color)
    
    # Calculate composite complexity score (0-1)
    complexity_score = _calculate_composite_complexity(
        legal_moves_count,
        captures_count,
        checks_count,
        pieces_attacked,
        material_imbalance,
        mobility,
    )
    
    return PositionComplexity(
        legal_moves_count=legal_moves_count,
        captures_available=captures_count,
        checks_available=checks_count,
        pieces_attacked=pieces_attacked,
        pieces_defending=pieces_defending,
        material_imbalance=material_imbalance,
        piece_mobility=mobility,
        complexity_score=complexity_score,
    )


def _calculate_composite_complexity(
    legal_moves: int,
    captures: int,
    checks: int,
    attacked: int,
    material_imbalance: int,
    mobility: float,
) -> float:
    """
    Calculate composite complexity score from individual factors.
    
    Returns 0-1 where:
    - 0.0-0.3 = Simple position (few options, clear best move)
    - 0.3-0.6 = Medium complexity
    - 0.6-1.0 = High complexity (many options, tactical tension)
    """
    score = 0.0
    
    # More legal moves = more complex (normalized to ~40 moves = max)
    score += min(0.3, (legal_moves / 40) * 0.3)
    
    # Captures available = tactical complexity
    score += min(0.2, (captures / 5) * 0.2)
    
    # Checks available = forcing moves complexity
    score += min(0.1, (checks / 3) * 0.1)
    
    # Pieces under attack = tension
    score += min(0.2, (attacked / 3) * 0.2)
    
    # Material imbalance = unusual position
    score += min(0.1, (material_imbalance / 500) * 0.1)
    
    # Low mobility can indicate trapped pieces (positional complexity)
    if mobility < 0.3:
        score += 0.1
    
    return min(1.0, score)


def analyze_game_complexity(pgn_text: str, player_color: str = "white") -> List[float]:
    """
    Analyze complexity of each position in a game.
    
    Args:
        pgn_text: PGN text of the game
        player_color: "white" or "black"
        
    Returns:
        List of complexity scores for each of the player's moves
    """
    import chess.pgn
    import io
    
    complexity_scores = []
    
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if not game:
            return []
        
        board = game.board()
        
        for move_num, node in enumerate(game.mainline(), 1):
            move = node.move
            
            is_player_move = (
                (player_color == "white" and (move_num % 2 == 1)) or
                (player_color == "black" and (move_num % 2 == 0))
            )
            
            if is_player_move:
                # Analyze position BEFORE the move
                complexity = analyze_position_complexity(board)
                complexity_scores.append(complexity.complexity_score)
            
            board.push(move)
        
        return complexity_scores
        
    except Exception as e:
        LOGGER.warning(f"Failed to analyze game complexity: {e}")
        return []


@dataclass
class GameComplexityStats:
    """Aggregate complexity statistics for a game."""
    avg_complexity: float
    max_complexity: float
    min_complexity: float
    high_complexity_moves: int  # Moves with complexity > 0.6
    low_complexity_moves: int  # Moves with complexity < 0.3
    total_moves: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "avg_complexity": round(self.avg_complexity, 3),
            "max_complexity": round(self.max_complexity, 3),
            "min_complexity": round(self.min_complexity, 3),
            "high_complexity_moves": self.high_complexity_moves,
            "low_complexity_moves": self.low_complexity_moves,
            "total_moves": self.total_moves,
        }


def get_complexity_stats(complexity_scores: List[float]) -> GameComplexityStats:
    """Calculate aggregate statistics from per-move complexity scores."""
    if not complexity_scores:
        return GameComplexityStats(
            avg_complexity=0.0,
            max_complexity=0.0,
            min_complexity=0.0,
            high_complexity_moves=0,
            low_complexity_moves=0,
            total_moves=0,
        )
    
    from statistics import mean
    
    return GameComplexityStats(
        avg_complexity=mean(complexity_scores),
        max_complexity=max(complexity_scores),
        min_complexity=min(complexity_scores),
        high_complexity_moves=sum(1 for c in complexity_scores if c > 0.6),
        low_complexity_moves=sum(1 for c in complexity_scores if c < 0.3),
        total_moves=len(complexity_scores),
    )
