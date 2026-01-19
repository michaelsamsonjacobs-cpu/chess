"""Opening Book Detection and Filtering.

Uses ECO (Encyclopedia of Chess Openings) codes to identify:
1. Whether moves are within known opening theory
2. The "novelty point" - first move that leaves known theory
3. Accurate engine agreement calculations that exclude book moves

Key insight from research:
- First 10-15 moves often have 100% engine agreement for prepared players
- This is NORMAL and should not count as suspicious
- Detection should focus on moves AFTER the novelty point

ECO Database Sources:
- Lichess opening database (CC0 license)
- SCID ECO database
- PolyGlot opening books
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
import chess
import chess.pgn
import io

LOGGER = logging.getLogger(__name__)

# Common opening book positions (FEN -> ECO code + name)
# This is a subset - can be expanded with full ECO database
OPENING_BOOK: Dict[str, Tuple[str, str]] = {}

# Standard opening moves that are considered "book" at various depths
# Key = FEN (position only, not full FEN)
# Value = (ECO code, opening name, expected moves count)

# We'll load a more comprehensive database, but here are common positions
BOOK_POSITIONS: Set[str] = set()


def _position_key(board: chess.Board) -> str:
    """Get position-only key from board (ignoring castling/ep for book lookup)."""
    return board.board_fen()


def initialize_opening_book():
    """
    Initialize the opening book database.
    
    Uses common opening positions that are well-known theory.
    For production, this should load from a proper ECO database file.
    """
    global BOOK_POSITIONS, OPENING_BOOK
    
    # Common opening lines (moves from starting position)
    common_lines = [
        # Italian Game
        "e4 e5 Nf3 Nc6 Bc4",
        "e4 e5 Nf3 Nc6 Bc4 Bc5",
        "e4 e5 Nf3 Nc6 Bc4 Nf6",
        # Ruy Lopez
        "e4 e5 Nf3 Nc6 Bb5",
        "e4 e5 Nf3 Nc6 Bb5 a6",
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4",
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6",
        # Sicilian
        "e4 c5",
        "e4 c5 Nf3",
        "e4 c5 Nf3 d6",
        "e4 c5 Nf3 Nc6",
        "e4 c5 Nf3 e6",
        "e4 c5 Nf3 d6 d4",
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4",
        # French
        "e4 e6",
        "e4 e6 d4",
        "e4 e6 d4 d5",
        "e4 e6 d4 d5 Nc3",
        "e4 e6 d4 d5 Nd2",
        "e4 e6 d4 d5 e5",
        # Caro-Kann
        "e4 c6",
        "e4 c6 d4",
        "e4 c6 d4 d5",
        "e4 c6 d4 d5 Nc3",
        "e4 c6 d4 d5 e5",
        # Queen's Gambit
        "d4 d5",
        "d4 d5 c4",
        "d4 d5 c4 e6",
        "d4 d5 c4 c6",
        "d4 d5 c4 dxc4",
        # King's Indian
        "d4 Nf6",
        "d4 Nf6 c4",
        "d4 Nf6 c4 g6",
        "d4 Nf6 c4 g6 Nc3",
        "d4 Nf6 c4 g6 Nc3 Bg7",
        # Nimzo-Indian
        "d4 Nf6 c4 e6",
        "d4 Nf6 c4 e6 Nc3",
        "d4 Nf6 c4 e6 Nc3 Bb4",
        # English
        "c4",
        "c4 e5",
        "c4 Nf6",
        "c4 c5",
        # London System
        "d4 d5 Bf4",
        "d4 Nf6 Bf4",
        # Scotch
        "e4 e5 Nf3 Nc6 d4",
        "e4 e5 Nf3 Nc6 d4 exd4",
        # Vienna
        "e4 e5 Nc3",
        # Scandinavian
        "e4 d5",
        "e4 d5 exd5",
        "e4 d5 exd5 Qxd5",
        # Pirc/Modern
        "e4 d6",
        "e4 g6",
        # Alekhine
        "e4 Nf6",
        # Dutch
        "d4 f5",
        # Benoni
        "d4 Nf6 c4 c5",
        # Grunfeld
        "d4 Nf6 c4 g6 Nc3 d5",
        # Slav
        "d4 d5 c4 c6",
        "d4 d5 c4 c6 Nf3",
        "d4 d5 c4 c6 Nc3",
    ]
    
    # Generate all positions from these lines
    for line in common_lines:
        board = chess.Board()
        moves = line.split()
        
        for i, move_san in enumerate(moves):
            try:
                move = board.parse_san(move_san)
                board.push(move)
                pos_key = _position_key(board)
                BOOK_POSITIONS.add(pos_key)
            except Exception as e:
                LOGGER.debug(f"Failed to parse move {move_san}: {e}")
                break
    
    LOGGER.info(f"Initialized opening book with {len(BOOK_POSITIONS)} positions")


def is_book_position(board: chess.Board) -> bool:
    """Check if current position is in the opening book."""
    if not BOOK_POSITIONS:
        initialize_opening_book()
    
    return _position_key(board) in BOOK_POSITIONS


def is_book_move(board: chess.Board, move: chess.Move) -> bool:
    """Check if a move leads to a book position."""
    if not BOOK_POSITIONS:
        initialize_opening_book()
    
    # Make the move temporarily
    board.push(move)
    in_book = _position_key(board) in BOOK_POSITIONS
    board.pop()
    
    return in_book


@dataclass
class OpeningAnalysis:
    """Analysis of opening phase for a game."""
    moves_in_book: int  # Number of moves that were book moves
    novelty_move_number: int  # Move number where player left book (0 if never)
    novelty_move: Optional[str]  # The first non-book move (SAN notation)
    opening_eco: Optional[str]  # ECO code if identified
    opening_name: Optional[str]  # Opening name if identified
    book_accuracy: float  # Accuracy during book phase (expected to be high)
    post_book_moves: int  # Number of moves after leaving book
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "moves_in_book": self.moves_in_book,
            "novelty_move_number": self.novelty_move_number,
            "novelty_move": self.novelty_move,
            "opening_eco": self.opening_eco,
            "opening_name": self.opening_name,
            "book_accuracy": round(self.book_accuracy, 3),
            "post_book_moves": self.post_book_moves,
        }


def analyze_opening(pgn_text: str, player_color: str = "white") -> Optional[OpeningAnalysis]:
    """
    Analyze the opening phase of a game.
    
    Args:
        pgn_text: PGN text of the game
        player_color: "white" or "black"
        
    Returns:
        OpeningAnalysis object or None if parsing fails
    """
    if not BOOK_POSITIONS:
        initialize_opening_book()
    
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if not game:
            return None
        
        board = game.board()
        moves_in_book = 0
        novelty_move_number = 0
        novelty_move = None
        total_moves = 0
        
        # Iterate through moves
        for move_num, node in enumerate(game.mainline(), 1):
            move = node.move
            total_moves += 1
            
            # Check if this is the player's move
            is_player_move = (
                (player_color == "white" and (move_num % 2 == 1)) or
                (player_color == "black" and (move_num % 2 == 0))
            )
            
            # Check if position before move is in book
            in_book = is_book_position(board)
            
            if in_book:
                if is_player_move:
                    moves_in_book += 1
            elif novelty_move_number == 0 and is_player_move:
                # First non-book move by this player
                novelty_move_number = move_num
                novelty_move = board.san(move)
            
            board.push(move)
        
        # Get opening info from PGN headers
        opening_eco = game.headers.get("ECO", None)
        opening_name = game.headers.get("Opening", None)
        
        # If we never left book, novelty is "none"
        post_book_moves = max(0, (total_moves // 2) - moves_in_book) if player_color == "white" else max(0, (total_moves // 2) - moves_in_book)
        
        return OpeningAnalysis(
            moves_in_book=moves_in_book,
            novelty_move_number=novelty_move_number,
            novelty_move=novelty_move,
            opening_eco=opening_eco,
            opening_name=opening_name,
            book_accuracy=1.0,  # Book moves are by definition "accurate"
            post_book_moves=post_book_moves,
        )
        
    except Exception as e:
        LOGGER.warning(f"Failed to analyze opening: {e}")
        return None


def get_moves_after_novelty(pgn_text: str, player_color: str = "white") -> List[chess.Move]:
    """
    Get all moves made by the player AFTER leaving opening book.
    
    These are the moves that should be evaluated for engine agreement.
    Book moves should not count toward suspicion.
    """
    if not BOOK_POSITIONS:
        initialize_opening_book()
    
    post_novelty_moves = []
    in_book = True
    
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
            
            if in_book:
                in_book = is_book_position(board)
            
            if not in_book and is_player_move:
                post_novelty_moves.append(move)
            
            board.push(move)
        
        return post_novelty_moves
        
    except Exception as e:
        LOGGER.warning(f"Failed to get post-novelty moves: {e}")
        return []


def calculate_adjusted_accuracy(
    all_moves_accuracy: List[float],
    moves_in_book: int,
) -> float:
    """
    Calculate engine agreement excluding book moves.
    
    This gives a more accurate picture of player skill
    by not counting the "free" accuracy from memorized openings.
    """
    if not all_moves_accuracy:
        return 0.0
    
    # Skip the first N moves (book moves)
    post_book_accuracy = all_moves_accuracy[moves_in_book:]
    
    if not post_book_accuracy:
        return 1.0  # All moves were book moves
    
    return sum(post_book_accuracy) / len(post_book_accuracy)


# Initialize book on module load
initialize_opening_book()
