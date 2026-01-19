"""Streak Improbability Score (SIS) Analysis.

Detects statistically improbable winning streaks based on:
1. ELO-based expected win probability
2. Combined probability of consecutive wins
3. Marathon session detection (games per hour)
4. Opponent strength thresholds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from statistics import mean

LOGGER = logging.getLogger(__name__)


@dataclass
class WinStreak:
    """Represents a detected winning streak."""
    start_index: int
    end_index: int
    length: int
    games: List[Dict[str, Any]]
    combined_probability: float
    improbability: float  # 1 / combined_probability (e.g., "1 in 10,000")
    avg_opponent_rating: float
    avg_player_rating: float
    is_marathon: bool  # True if games played rapidly
    games_per_hour: float
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    

@dataclass 
class StreakAnalysisResult:
    """Results of streak improbability analysis."""
    total_games: int
    win_count: int
    loss_count: int
    draw_count: int
    longest_win_streak: int
    suspicious_streaks: List[WinStreak]
    max_improbability: float
    total_marathon_games: int
    streak_improbability_score: float  # 0.0 = normal, 1.0 = extremely suspicious
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_games": self.total_games,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "draw_count": self.draw_count,
            "longest_win_streak": self.longest_win_streak,
            "suspicious_streak_count": len(self.suspicious_streaks),
            "max_improbability": self.max_improbability,
            "total_marathon_games": self.total_marathon_games,
            "streak_improbability_score": round(self.streak_improbability_score, 4),
            "suspicious_streaks": [
                {
                    "length": s.length,
                    "improbability": s.improbability,
                    "avg_opponent_rating": round(s.avg_opponent_rating),
                    "is_marathon": s.is_marathon,
                    "games_per_hour": round(s.games_per_hour, 1) if s.games_per_hour else None,
                }
                for s in self.suspicious_streaks[:5]  # Top 5 most suspicious
            ],
        }


def elo_expected_score(player_rating: float, opponent_rating: float) -> float:
    """
    Calculate expected score using the ELO formula.
    
    Returns a value between 0 and 1:
    - 0.5 = equal ratings (50% win expectancy)
    - Higher = player expected to win more
    - Lower = player expected to lose more
    
    Formula: E = 1 / (1 + 10^((Ro - Rp) / 400))
    """
    if player_rating <= 0 or opponent_rating <= 0:
        return 0.5
    
    exponent = (opponent_rating - player_rating) / 400.0
    return 1.0 / (1.0 + pow(10, exponent))


def calculate_win_probability(player_rating: float, opponent_rating: float) -> float:
    """
    Convert expected score to win probability.
    
    Expected score includes draws, so we estimate:
    - Win prob = E - (draw_rate / 2)
    
    For simplicity, we use a simplified model:
    - Win probability ≈ expected_score (slightly optimistic for high ELO diff)
    """
    expected = elo_expected_score(player_rating, opponent_rating)
    
    # Apply a small penalty for draws (assume 10% draw rate in blitz)
    # This means you need to win, not just perform well
    draw_rate = 0.10
    win_prob = expected * (1 - draw_rate / 2)
    
    # Cap at 0.95 - no one has 100% win rate even against weaker players
    return min(0.95, max(0.01, win_prob))


def find_win_streaks(games: List[Dict[str, Any]], player_username: str, min_length: int = 5) -> List[WinStreak]:
    """
    Find all winning streaks of at least min_length consecutive wins.
    
    Args:
        games: List of game dicts from Chess.com/Lichess API
        player_username: The player we're analyzing
        min_length: Minimum streak length to track
        
    Returns:
        List of WinStreak objects
    """
    if not games:
        return []
    
    # Sort games by end time (oldest first)
    sorted_games = sorted(games, key=lambda g: g.get('end_time', 0))
    
    streaks = []
    current_streak = []
    current_streak_start = 0
    
    for i, game in enumerate(sorted_games):
        is_win = _is_player_win(game, player_username)
        
        if is_win:
            if not current_streak:
                current_streak_start = i
            current_streak.append(game)
        else:
            # Streak broken - check if it's long enough
            if len(current_streak) >= min_length:
                streak = _create_streak(
                    current_streak, 
                    current_streak_start, 
                    i - 1, 
                    player_username
                )
                if streak:
                    streaks.append(streak)
            current_streak = []
    
    # Check final streak
    if len(current_streak) >= min_length:
        streak = _create_streak(
            current_streak, 
            current_streak_start, 
            len(sorted_games) - 1, 
            player_username
        )
        if streak:
            streaks.append(streak)
    
    return streaks


def _is_player_win(game: Dict[str, Any], username: str) -> bool:
    """Determine if the player won this game."""
    username_lower = username.lower()
    
    # Chess.com format
    if 'white' in game and 'black' in game:
        white = game.get('white', {})
        black = game.get('black', {})
        
        white_username = white.get('username', '').lower() if isinstance(white, dict) else ''
        black_username = black.get('username', '').lower() if isinstance(black, dict) else ''
        
        if white_username == username_lower:
            return white.get('result') == 'win' if isinstance(white, dict) else False
        elif black_username == username_lower:
            return black.get('result') == 'win' if isinstance(black, dict) else False
    
    # Lichess format
    if 'winner' in game:
        players = game.get('players', {})
        white = players.get('white', {})
        black = players.get('black', {})
        
        white_id = white.get('user', {}).get('id', '').lower()
        black_id = black.get('user', {}).get('id', '').lower()
        
        if white_id == username_lower:
            return game.get('winner') == 'white'
        elif black_id == username_lower:
            return game.get('winner') == 'black'
    
    return False


def _get_ratings(game: Dict[str, Any], username: str) -> Tuple[float, float]:
    """Extract player and opponent ratings from game."""
    username_lower = username.lower()
    
    # Chess.com format
    if 'white' in game and 'black' in game:
        white = game.get('white', {})
        black = game.get('black', {})
        
        if isinstance(white, dict) and isinstance(black, dict):
            white_username = white.get('username', '').lower()
            white_rating = white.get('rating', 1500)
            black_username = black.get('username', '').lower()
            black_rating = black.get('rating', 1500)
            
            if white_username == username_lower:
                return float(white_rating), float(black_rating)
            elif black_username == username_lower:
                return float(black_rating), float(white_rating)
    
    # Lichess format
    players = game.get('players', {})
    if players:
        white = players.get('white', {})
        black = players.get('black', {})
        
        white_id = white.get('user', {}).get('id', '').lower()
        white_rating = white.get('rating', 1500)
        black_id = black.get('user', {}).get('id', '').lower()
        black_rating = black.get('rating', 1500)
        
        if white_id == username_lower:
            return float(white_rating), float(black_rating)
        elif black_id == username_lower:
            return float(black_rating), float(white_rating)
    
    return 1500.0, 1500.0


def _get_game_time(game: Dict[str, Any]) -> Optional[datetime]:
    """Extract game end time."""
    # Chess.com format (Unix timestamp)
    end_time = game.get('end_time')
    if end_time and isinstance(end_time, (int, float)):
        return datetime.fromtimestamp(end_time)
    
    # Lichess format (milliseconds)
    created_at = game.get('createdAt')
    if created_at and isinstance(created_at, (int, float)):
        return datetime.fromtimestamp(created_at / 1000)
    
    return None


def _create_streak(
    games: List[Dict[str, Any]], 
    start_idx: int, 
    end_idx: int, 
    username: str
) -> Optional[WinStreak]:
    """Create a WinStreak object from a list of consecutive wins."""
    if not games:
        return None
    
    # Calculate combined probability
    combined_prob = 1.0
    player_ratings = []
    opponent_ratings = []
    
    for game in games:
        player_rating, opponent_rating = _get_ratings(game, username)
        player_ratings.append(player_rating)
        opponent_ratings.append(opponent_rating)
        
        win_prob = calculate_win_probability(player_rating, opponent_rating)
        combined_prob *= win_prob
    
    # Calculate marathon metrics
    start_time = _get_game_time(games[0])
    end_time = _get_game_time(games[-1])
    
    games_per_hour = 0.0
    is_marathon = False
    
    if start_time and end_time and start_time != end_time:
        duration_hours = (end_time - start_time).total_seconds() / 3600
        if duration_hours > 0:
            games_per_hour = len(games) / duration_hours
            # Marathon = playing more than 8 games per hour for 5+ games
            is_marathon = games_per_hour > 8 and len(games) >= 5
    
    # Calculate improbability
    improbability = 1.0 / combined_prob if combined_prob > 0 else float('inf')
    
    return WinStreak(
        start_index=start_idx,
        end_index=end_idx,
        length=len(games),
        games=games,
        combined_probability=combined_prob,
        improbability=improbability,
        avg_opponent_rating=mean(opponent_ratings) if opponent_ratings else 1500,
        avg_player_rating=mean(player_ratings) if player_ratings else 1500,
        is_marathon=is_marathon,
        games_per_hour=games_per_hour,
        start_time=start_time,
        end_time=end_time,
    )


def analyze_streaks(
    games: List[Dict[str, Any]], 
    username: str,
    min_streak_length: int = 5,
    suspicion_threshold: float = 10000,  # 1 in 10,000
    high_rating_threshold: int = 2400,   # Consider opponents above this "strong"
) -> StreakAnalysisResult:
    """
    Perform full streak improbability analysis.
    
    Args:
        games: List of game data from Chess.com/Lichess
        username: Player being analyzed
        min_streak_length: Minimum consecutive wins to track
        suspicion_threshold: Flag streaks with improbability > this value
        high_rating_threshold: Consider streaks against opponents > this as high-value
        
    Returns:
        StreakAnalysisResult with all analysis data
    """
    if not games:
        return StreakAnalysisResult(
            total_games=0,
            win_count=0,
            loss_count=0,
            draw_count=0,
            longest_win_streak=0,
            suspicious_streaks=[],
            max_improbability=0,
            total_marathon_games=0,
            streak_improbability_score=0.0,
        )
    
    # Count wins/losses/draws
    win_count = sum(1 for g in games if _is_player_win(g, username))
    loss_count = sum(1 for g in games if _is_player_loss(g, username))
    draw_count = len(games) - win_count - loss_count
    
    # Find all streaks
    all_streaks = find_win_streaks(games, username, min_streak_length)
    
    # Find longest streak
    longest_streak = max([s.length for s in all_streaks], default=0)
    
    # Filter suspicious streaks
    suspicious_streaks = [
        s for s in all_streaks
        if s.improbability >= suspicion_threshold or 
           (s.is_marathon and s.improbability >= suspicion_threshold / 10) or
           (s.avg_opponent_rating >= high_rating_threshold and s.improbability >= suspicion_threshold / 5)
    ]
    
    # Sort by improbability (most suspicious first)
    suspicious_streaks.sort(key=lambda s: s.improbability, reverse=True)
    
    # Calculate max improbability
    max_improbability = max([s.improbability for s in suspicious_streaks], default=0)
    
    # Count marathon games
    total_marathon_games = sum(s.length for s in all_streaks if s.is_marathon)
    
    # Calculate overall score (0.0 - 1.0)
    streak_score = _calculate_streak_score(
        suspicious_streaks, 
        max_improbability, 
        total_marathon_games,
        len(games)
    )
    
    return StreakAnalysisResult(
        total_games=len(games),
        win_count=win_count,
        loss_count=loss_count,
        draw_count=draw_count,
        longest_win_streak=longest_streak,
        suspicious_streaks=suspicious_streaks,
        max_improbability=max_improbability,
        total_marathon_games=total_marathon_games,
        streak_improbability_score=streak_score,
    )


def _is_player_loss(game: Dict[str, Any], username: str) -> bool:
    """Determine if the player lost this game."""
    username_lower = username.lower()
    
    # Chess.com format
    if 'white' in game and 'black' in game:
        white = game.get('white', {})
        black = game.get('black', {})
        
        if isinstance(white, dict) and isinstance(black, dict):
            white_username = white.get('username', '').lower()
            black_username = black.get('username', '').lower()
            
            if white_username == username_lower:
                return black.get('result') == 'win'
            elif black_username == username_lower:
                return white.get('result') == 'win'
    
    return False


def _calculate_streak_score(
    suspicious_streaks: List[WinStreak],
    max_improbability: float,
    marathon_games: int,
    total_games: int,
) -> float:
    """
    Calculate overall streak improbability score (0.0 - 1.0).
    
    Factors:
    - Number of suspicious streaks
    - Maximum improbability level
    - Marathon game percentage
    """
    if not suspicious_streaks or total_games == 0:
        return 0.0
    
    # Base score from max improbability (log scale)
    # 1 in 1000 = 0.2, 1 in 10000 = 0.4, 1 in 100000 = 0.6, 1 in 1000000 = 0.8
    import math
    if max_improbability > 1:
        log_improbability = math.log10(max_improbability)
        improbability_component = min(1.0, log_improbability / 7)  # 7 = 1 in 10 million
    else:
        improbability_component = 0.0
    
    # Bonus for multiple suspicious streaks
    streak_count_component = min(0.3, len(suspicious_streaks) * 0.1)
    
    # Marathon penalty
    marathon_ratio = marathon_games / total_games if total_games > 0 else 0
    marathon_component = min(0.2, marathon_ratio * 0.5)
    
    # Strong opponent bonus
    strong_streaks = [s for s in suspicious_streaks if s.avg_opponent_rating >= 2400]
    strong_component = min(0.2, len(strong_streaks) * 0.1)
    
    total_score = improbability_component + streak_count_component + marathon_component + strong_component
    
    return min(1.0, total_score)
