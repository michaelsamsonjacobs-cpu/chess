"""Timing Anomaly Analysis for Cheat Detection.

Detects suspicious timing patterns that may indicate engine assistance:
1. Time-complexity correlation (humans think longer on complex positions)
2. Opening hesitation (unusual delays on book moves)
3. Obvious move delays (waiting too long on forced moves)
4. Time variance coefficient (humans have varied thinking times)
5. Time entropy (low entropy = robotic timing)

Research basis:
- Human move times follow log-normal distribution
- Positive correlation between position complexity and think time
- Cheaters often show uniform timing or negative correlation
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from statistics import mean, stdev, variance, median

LOGGER = logging.getLogger(__name__)


@dataclass
class TimingMetrics:
    """Calculated timing metrics for a single game."""
    total_moves: int
    avg_move_time: float
    median_move_time: float
    time_variance: float
    time_stdev: float
    coefficient_of_variation: float  # stdev / mean - low = suspicious
    time_entropy: float  # Shannon entropy of time distribution
    
    # Anomaly indicators
    opening_hesitation_count: int  # Delays > 5s on first 10 moves
    obvious_move_delay_count: int  # Long thinks on recaptures/forced moves
    uniform_timing_score: float  # 0 = varied, 1 = robotic
    
    # Time-complexity correlation (requires position eval data)
    time_complexity_correlation: Optional[float]  # Positive = human, negative = suspicious
    
    # Time Scramble Detection (low time + high accuracy = suspicious)
    scramble_moves_count: int  # Moves made with < 10 seconds on clock
    scramble_accuracy: Optional[float]  # Engine agreement % during scramble (if available)
    scramble_toggle_score: float  # 0 = normal, 1 = suspicious toggle pattern
    
    # Overall suspicion score
    timing_suspicion_score: float  # 0.0 - 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_moves": self.total_moves,
            "avg_move_time": round(self.avg_move_time, 2),
            "median_move_time": round(self.median_move_time, 2),
            "time_variance": round(self.time_variance, 2),
            "coefficient_of_variation": round(self.coefficient_of_variation, 3),
            "time_entropy": round(self.time_entropy, 3),
            "opening_hesitation_count": self.opening_hesitation_count,
            "obvious_move_delay_count": self.obvious_move_delay_count,
            "uniform_timing_score": round(self.uniform_timing_score, 3),
            "time_complexity_correlation": round(self.time_complexity_correlation, 3) if self.time_complexity_correlation else None,
            "scramble_moves_count": self.scramble_moves_count,
            "scramble_accuracy": round(self.scramble_accuracy, 3) if self.scramble_accuracy else None,
            "scramble_toggle_score": round(self.scramble_toggle_score, 3),
            "timing_suspicion_score": round(self.timing_suspicion_score, 3),
        }


def extract_move_times_chesscom(game: Dict[str, Any], player_color: str) -> List[float]:
    """
    Extract move times from Chess.com game data.
    
    Chess.com includes clock times in PGN comments like {[%clk 0:04:52.3]}
    For each move, we calculate: time_before - time_after = think_time
    """
    pgn = game.get("pgn", "")
    if not pgn:
        return []
    
    import re
    
    # Extract all clock times from PGN
    clock_pattern = r'\[%clk (\d+):(\d+):(\d+\.?\d*)\]'
    clocks = re.findall(clock_pattern, pgn)
    
    if len(clocks) < 2:
        return []
    
    # Convert to seconds
    clock_seconds = []
    for h, m, s in clocks:
        total = int(h) * 3600 + int(m) * 60 + float(s)
        clock_seconds.append(total)
    
    # Separate by color (white = even indices, black = odd)
    if player_color == "white":
        player_clocks = clock_seconds[0::2]
    else:
        player_clocks = clock_seconds[1::2]
    
    # Calculate think times (difference between consecutive clocks)
    think_times = []
    for i in range(1, len(player_clocks)):
        think_time = player_clocks[i-1] - player_clocks[i]
        # Handle increments (time can go up)
        if think_time < 0:
            think_time = 0
        think_times.append(think_time)
    
    return think_times


def extract_move_times_lichess(game: Dict[str, Any], player_color: str) -> List[float]:
    """
    Extract move times from Lichess game data.
    
    Lichess provides clocks array directly in the JSON response.
    """
    clocks = game.get("clocks", [])
    if not clocks or len(clocks) < 2:
        return []
    
    # Convert centiseconds to seconds
    clock_seconds = [c / 100.0 for c in clocks]
    
    # Separate by color
    if player_color == "white":
        player_clocks = clock_seconds[0::2]
    else:
        player_clocks = clock_seconds[1::2]
    
    # Calculate think times
    think_times = []
    for i in range(1, len(player_clocks)):
        think_time = player_clocks[i-1] - player_clocks[i]
        if think_time < 0:
            think_time = 0
        think_times.append(think_time)
    
    return think_times


def calculate_time_entropy(times: List[float], bins: int = 10) -> float:
    """
    Calculate Shannon entropy of time distribution.
    
    Low entropy = times clustered in few bins = robotic
    High entropy = times spread across bins = human
    """
    if not times or len(times) < 5:
        return 0.0
    
    # Create histogram
    min_time = min(times)
    max_time = max(times)
    
    if max_time == min_time:
        return 0.0
    
    bin_width = (max_time - min_time) / bins
    histogram = [0] * bins
    
    for t in times:
        bin_idx = min(int((t - min_time) / bin_width), bins - 1)
        histogram[bin_idx] += 1
    
    # Calculate entropy
    total = len(times)
    entropy = 0.0
    
    for count in histogram:
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    
    # Normalize to 0-1 (max entropy = log2(bins))
    max_entropy = math.log2(bins)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def detect_opening_hesitation(times: List[float], threshold: float = 5.0, opening_moves: int = 10) -> int:
    """
    Count moves in opening where player hesitated unusually long.
    
    In opening theory, most moves should be quick (book moves).
    Hesitation on well-known positions may indicate checking an engine.
    """
    if len(times) < opening_moves:
        opening_moves = len(times)
    
    hesitation_count = 0
    for i in range(min(opening_moves, len(times))):
        if times[i] > threshold:
            hesitation_count += 1
    
    return hesitation_count


def detect_obvious_move_delays(
    times: List[float], 
    moves: List[str] = None,
    long_think_threshold: float = 10.0
) -> int:
    """
    Count times when player took unusually long on "obvious" moves.
    
    Obvious moves include:
    - Recaptures (piece just taken)
    - Only legal move
    - Check responses
    
    Without move analysis, we use heuristic: very long thinks early in game
    when time is plentiful are suspicious.
    """
    if not times:
        return 0
    
    # Heuristic: if first 15 moves have any > 10 second thinks
    # when total game time is still high, flag as suspicious
    delay_count = 0
    check_moves = min(15, len(times))
    
    for i in range(check_moves):
        if times[i] > long_think_threshold:
            delay_count += 1
    
    return delay_count


def calculate_uniform_timing_score(times: List[float]) -> float:
    """
    Calculate how "uniform" the timing is.
    
    0.0 = highly varied (human-like)
    1.0 = very uniform (robotic)
    
    Uses coefficient of variation: stdev / mean
    Humans typically have CV > 0.5, robots < 0.2
    """
    if not times or len(times) < 5:
        return 0.0
    
    avg = mean(times)
    if avg == 0:
        return 0.0
    
    std = stdev(times) if len(times) > 1 else 0
    cv = std / avg
    
    # Convert to 0-1 score (lower CV = higher uniformity score)
    # CV of 0.2 = very uniform (score 0.8)
    # CV of 0.8 = varied (score 0.2)
    uniformity = max(0, 1 - (cv / 1.0))
    return min(1.0, uniformity)


def detect_time_scramble(
    clock_times: List[float],
    move_accuracies: List[float] = None,
    scramble_threshold: float = 10.0,  # seconds remaining
) -> Tuple[int, Optional[float], float]:
    """
    Detect suspicious accuracy during time scramble.
    
    Key insight: Human accuracy should DROP when near zero time,
    as players premove and guess. Engine assistance maintains high accuracy.
    
    Args:
        clock_times: Remaining clock time at each move
        move_accuracies: Optional accuracy per move (0-1, engine agreement)
        scramble_threshold: Clock time below which we're "in scramble"
        
    Returns:
        Tuple of (scramble_moves_count, scramble_accuracy, scramble_toggle_score)
    """
    if not clock_times:
        return 0, None, 0.0
    
    # Find moves made under time pressure
    scramble_indices = [i for i, t in enumerate(clock_times) if t < scramble_threshold]
    scramble_count = len(scramble_indices)
    
    if scramble_count == 0:
        return 0, None, 0.0
    
    scramble_accuracy = None
    toggle_score = 0.0
    
    if move_accuracies and len(move_accuracies) == len(clock_times):
        # Calculate accuracy during scramble vs non-scramble
        scramble_accs = [move_accuracies[i] for i in scramble_indices if i < len(move_accuracies)]
        non_scramble_indices = [i for i, t in enumerate(clock_times) if t >= scramble_threshold]
        non_scramble_accs = [move_accuracies[i] for i in non_scramble_indices if i < len(move_accuracies)]
        
        if scramble_accs:
            scramble_accuracy = mean(scramble_accs)
            
            # Compare to non-scramble accuracy
            if non_scramble_accs:
                non_scramble_accuracy = mean(non_scramble_accs)
                
                # SUSPICIOUS: Accuracy INCREASES or stays same during scramble
                # Normal humans: accuracy drops by 10-30% under time pressure
                if scramble_accuracy >= non_scramble_accuracy:
                    # Very suspicious - maintained or improved accuracy
                    toggle_score = 0.8
                elif scramble_accuracy > non_scramble_accuracy - 0.1:
                    # Somewhat suspicious - minimal accuracy drop
                    toggle_score = 0.4
                else:
                    # Normal - accuracy dropped significantly
                    toggle_score = 0.0
                
                # Extra suspicious if scramble accuracy is very high (>80%)
                if scramble_accuracy > 0.8:
                    toggle_score = min(1.0, toggle_score + 0.2)
    else:
        # Without accuracy data, just flag high scramble move count
        if scramble_count > 15:
            toggle_score = 0.3  # Many moves in scramble, could be suspicious
    
    return scramble_count, scramble_accuracy, toggle_score

def calculate_timing_suspicion(metrics: TimingMetrics) -> float:
    """
    Calculate overall timing suspicion score (0.0 - 1.0).
    
    Weights various factors to produce a single score.
    """
    suspicion = 0.0
    
    # Uniform timing is suspicious
    if metrics.uniform_timing_score > 0.7:
        suspicion += 0.3
    elif metrics.uniform_timing_score > 0.5:
        suspicion += 0.15
    
    # Low entropy is suspicious
    if metrics.time_entropy < 0.3:
        suspicion += 0.25
    elif metrics.time_entropy < 0.5:
        suspicion += 0.1
    
    # Opening hesitation is suspicious
    if metrics.opening_hesitation_count >= 5:
        suspicion += 0.2
    elif metrics.opening_hesitation_count >= 3:
        suspicion += 0.1
    
    # Obvious move delays are suspicious
    if metrics.obvious_move_delay_count >= 5:
        suspicion += 0.15
    elif metrics.obvious_move_delay_count >= 2:
        suspicion += 0.05
    
    # Negative time-complexity correlation is very suspicious
    if metrics.time_complexity_correlation is not None:
        if metrics.time_complexity_correlation < -0.2:
            suspicion += 0.3
        elif metrics.time_complexity_correlation < 0:
            suspicion += 0.1
    
    # Scramble toggle is highly suspicious (engine assistance in time pressure)
    if metrics.scramble_toggle_score > 0.6:
        suspicion += 0.35
    elif metrics.scramble_toggle_score > 0.3:
        suspicion += 0.15
    
    return min(1.0, suspicion)


def analyze_game_timing(
    game: Dict[str, Any],
    player_username: str,
    source: str = "chesscom",
    complexity_scores: List[float] = None,
) -> Optional[TimingMetrics]:
    """
    Perform complete timing analysis on a single game.
    
    Args:
        game: Game data from Chess.com or Lichess
        player_username: Username of player to analyze
        source: "chesscom" or "lichess"
        complexity_scores: Optional list of position complexity values per move
        
    Returns:
        TimingMetrics object or None if timing data unavailable
    """
    # Determine player color
    player_color = None
    username_lower = player_username.lower()
    
    if source == "chesscom":
        white = game.get("white", {})
        black = game.get("black", {})
        if isinstance(white, dict) and white.get("username", "").lower() == username_lower:
            player_color = "white"
        elif isinstance(black, dict) and black.get("username", "").lower() == username_lower:
            player_color = "black"
    else:  # lichess
        players = game.get("players", {})
        white_id = players.get("white", {}).get("user", {}).get("id", "").lower()
        black_id = players.get("black", {}).get("user", {}).get("id", "").lower()
        if white_id == username_lower:
            player_color = "white"
        elif black_id == username_lower:
            player_color = "black"
    
    if not player_color:
        return None
    
    # Extract move times
    if source == "chesscom":
        times = extract_move_times_chesscom(game, player_color)
    else:
        times = extract_move_times_lichess(game, player_color)
    
    if not times or len(times) < 5:
        return None
    
    # Calculate basic statistics
    avg_time = mean(times)
    med_time = median(times)
    var_time = variance(times) if len(times) > 1 else 0
    std_time = stdev(times) if len(times) > 1 else 0
    cv = std_time / avg_time if avg_time > 0 else 0
    
    # Calculate derived metrics
    entropy = calculate_time_entropy(times)
    opening_hesitation = detect_opening_hesitation(times)
    obvious_delays = detect_obvious_move_delays(times)
    uniform_score = calculate_uniform_timing_score(times)
    
    # Calculate time-complexity correlation if complexity data provided
    time_complexity_corr = None
    if complexity_scores and len(complexity_scores) == len(times):
        time_complexity_corr = _calculate_correlation(times, complexity_scores)
    
    # Extract clock times for scramble detection
    if source == "chesscom":
        clock_pattern = r'\[%clk (\d+):(\d+):(\d+\.?\d*)\]'
        import re
        clocks = re.findall(clock_pattern, game.get("pgn", ""))
        clock_seconds = []
        for h, m, s in clocks:
            total = int(h) * 3600 + int(m) * 60 + float(s)
            clock_seconds.append(total)
        
        if player_color == "white":
            player_clocks = clock_seconds[0::2]
        else:
            player_clocks = clock_seconds[1::2]
    else: # lichess
        l_clocks = game.get("clocks", [])
        if player_color == "white":
            player_clocks = [c/100.0 for c in l_clocks[0::2]]
        else:
            player_clocks = [c/100.0 for c in l_clocks[1::2]]

    # Detect time scramble (heuristics)
    # Note: move_accuracies not yet passed here, will be updated in future iteration
    scramble_count, scramble_acc, scramble_toggle = detect_time_scramble(player_clocks)

    # Build metrics object
    metrics = TimingMetrics(
        total_moves=len(times),
        avg_move_time=avg_time,
        median_move_time=med_time,
        time_variance=var_time,
        time_stdev=std_time,
        coefficient_of_variation=cv,
        time_entropy=entropy,
        opening_hesitation_count=opening_hesitation,
        obvious_move_delay_count=obvious_delays,
        uniform_timing_score=uniform_score,
        time_complexity_correlation=time_complexity_corr,
        scramble_moves_count=scramble_count,
        scramble_accuracy=scramble_acc,
        scramble_toggle_score=scramble_toggle,
        timing_suspicion_score=0.0,  # Placeholder
    )
    
    # Calculate overall suspicion
    metrics.timing_suspicion_score = calculate_timing_suspicion(metrics)
    
    return metrics


def _calculate_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation coefficient between two lists."""
    if len(x) != len(y) or len(x) < 3:
        return 0.0
    
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    
    sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(n))
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    
    if denominator == 0:
        return 0.0
    
    return numerator / denominator


@dataclass
class AggregateTimingResult:
    """Aggregate timing analysis across multiple games."""
    total_games_analyzed: int
    games_with_timing_data: int
    avg_timing_suspicion: float
    max_timing_suspicion: float
    total_opening_hesitations: int
    total_obvious_delays: int
    avg_coefficient_of_variation: float
    avg_time_entropy: float
    suspicious_game_count: int  # Games with suspicion > 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_games_analyzed": self.total_games_analyzed,
            "games_with_timing_data": self.games_with_timing_data,
            "avg_timing_suspicion": round(self.avg_timing_suspicion, 3),
            "max_timing_suspicion": round(self.max_timing_suspicion, 3),
            "total_opening_hesitations": self.total_opening_hesitations,
            "total_obvious_delays": self.total_obvious_delays,
            "avg_coefficient_of_variation": round(self.avg_coefficient_of_variation, 3),
            "avg_time_entropy": round(self.avg_time_entropy, 3),
            "suspicious_game_count": self.suspicious_game_count,
        }


def analyze_player_timing(
    games: List[Dict[str, Any]],
    username: str,
    source: str = "chesscom",
) -> AggregateTimingResult:
    """
    Analyze timing patterns across all games for a player.
    
    Returns aggregate metrics that can flag systematic timing anomalies.
    """
    all_metrics: List[TimingMetrics] = []
    
    for game in games:
        metrics = analyze_game_timing(game, username, source)
        if metrics:
            all_metrics.append(metrics)
    
    if not all_metrics:
        return AggregateTimingResult(
            total_games_analyzed=len(games),
            games_with_timing_data=0,
            avg_timing_suspicion=0.0,
            max_timing_suspicion=0.0,
            total_opening_hesitations=0,
            total_obvious_delays=0,
            avg_coefficient_of_variation=0.0,
            avg_time_entropy=0.0,
            suspicious_game_count=0,
        )
    
    # Aggregate metrics
    suspicion_scores = [m.timing_suspicion_score for m in all_metrics]
    cv_scores = [m.coefficient_of_variation for m in all_metrics]
    entropy_scores = [m.time_entropy for m in all_metrics]
    
    return AggregateTimingResult(
        total_games_analyzed=len(games),
        games_with_timing_data=len(all_metrics),
        avg_timing_suspicion=mean(suspicion_scores),
        max_timing_suspicion=max(suspicion_scores),
        total_opening_hesitations=sum(m.opening_hesitation_count for m in all_metrics),
        total_obvious_delays=sum(m.obvious_move_delay_count for m in all_metrics),
        avg_coefficient_of_variation=mean(cv_scores),
        avg_time_entropy=mean(entropy_scores),
        suspicious_game_count=sum(1 for s in suspicion_scores if s > 0.5),
    )
