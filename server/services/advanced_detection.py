"""
Advanced Detection Signals

Additional detection methods for comprehensive cheat detection:
1. Opening Repertoire Analysis - Sudden mastery of complex openings
2. Resignation Pattern Analysis - Never blunder-resigning is suspicious
3. Critical Moment Accuracy - Performance in critical positions only
4. Time Usage Distribution - Statistical analysis of move times
5. Opponent Correlation - Performance scaling with opponent strength
6. Session Analysis - Performance decline over playing sessions
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from statistics import mean, stdev, median
from collections import Counter

import chess

LOGGER = logging.getLogger(__name__)


# ============================================
# 1. Opening Repertoire Analysis
# ============================================

@dataclass
class OpeningAnalysis:
    """Analysis of opening repertoire patterns."""
    unique_openings: int  # Number of different openings played
    avg_opening_depth: float  # Average book move depth
    complex_opening_accuracy: float  # Accuracy in complex/rare openings
    repertoire_breadth: float  # 0-1, how varied the openings are
    suspicious_score: float  # 0-1


def analyze_opening_repertoire(
    games_data: List[Dict],
    opening_book_moves: int = 10,
) -> OpeningAnalysis:
    """
    Analyze player's opening repertoire for suspicious patterns.
    
    Suspicious: Playing many different complex openings perfectly
    Normal: Sticking to a few openings with natural mistakes
    """
    if not games_data:
        return OpeningAnalysis(0, 0.0, 0.0, 0.0, 0.0)
    
    openings = []
    opening_accuracies = []
    
    for game in games_data:
        opening = game.get("opening", "Unknown")
        openings.append(opening)
        
        # Accuracy in first N moves
        moves = game.get("moves", [])[:opening_book_moves]
        if moves:
            accuracies = [m.get("accuracy", 0.5) for m in moves if "accuracy" in m]
            if accuracies:
                opening_accuracies.append(mean(accuracies))
    
    unique_openings = len(set(openings))
    opening_counts = Counter(openings)
    
    # Breadth: entropy of opening distribution
    total = len(openings)
    if total > 0:
        probs = [c / total for c in opening_counts.values()]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(max(1, unique_openings))
        repertoire_breadth = entropy / max_entropy if max_entropy > 0 else 0
    else:
        repertoire_breadth = 0.0
    
    avg_opening_depth = opening_book_moves  # Placeholder
    complex_accuracy = mean(opening_accuracies) if opening_accuracies else 0.5
    
    # Suspicious: High accuracy + high variety
    variety_factor = min(1.0, unique_openings / 20)  # 20+ openings = max
    accuracy_factor = max(0, complex_accuracy - 0.7) / 0.3  # Above 70% is suspicious
    
    suspicious_score = variety_factor * accuracy_factor * 0.8
    
    return OpeningAnalysis(
        unique_openings=unique_openings,
        avg_opening_depth=avg_opening_depth,
        complex_opening_accuracy=complex_accuracy,
        repertoire_breadth=repertoire_breadth,
        suspicious_score=suspicious_score,
    )


# ============================================
# 2. Resignation Pattern Analysis
# ============================================

@dataclass
class ResignationAnalysis:
    """Analysis of resignation/game ending patterns."""
    total_games: int
    resignations: int
    timeouts: int
    checkmates_given: int
    checkmates_received: int
    blunder_losses: int  # Lost after a clear blunder
    clean_losses: int  # Lost without major blunders (resigned in -3 or worse)
    never_blunder_resign: bool  # Suspicious if true
    suspicious_score: float


def analyze_resignation_patterns(
    games_data: List[Dict],
) -> ResignationAnalysis:
    """
    Analyze how games end for suspicious patterns.
    
    Suspicious: Never losing to blunders, always resigning cleanly
    Normal: Mix of blunders, timeouts, and clean losses
    """
    if not games_data:
        return ResignationAnalysis(0, 0, 0, 0, 0, 0, 0, False, 0.0)
    
    resignations = 0
    timeouts = 0
    checkmates_given = 0
    checkmates_received = 0
    blunder_losses = 0
    clean_losses = 0
    
    for game in games_data:
        result = game.get("result", "")
        termination = game.get("termination", "").lower()
        is_win = game.get("is_player_win", False)
        final_eval = game.get("final_eval", 0)
        had_blunder = game.get("player_blundered", False)
        
        if "resign" in termination:
            resignations += 1
        elif "time" in termination:
            timeouts += 1
        elif "checkmate" in termination:
            if is_win:
                checkmates_given += 1
            else:
                checkmates_received += 1
        
        if not is_win:
            if had_blunder:
                blunder_losses += 1
            else:
                clean_losses += 1
    
    total_games = len(games_data)
    total_losses = blunder_losses + clean_losses + checkmates_received + timeouts
    
    # Never blunder-resigning is suspicious
    never_blunder_resign = blunder_losses == 0 and total_losses > 5
    
    # Calculate suspicion
    if total_losses > 0:
        clean_loss_ratio = clean_losses / total_losses
        # High ratio of clean losses = suspicious
        suspicious_score = clean_loss_ratio * 0.6
        if never_blunder_resign:
            suspicious_score += 0.3
    else:
        suspicious_score = 0.0
    
    return ResignationAnalysis(
        total_games=total_games,
        resignations=resignations,
        timeouts=timeouts,
        checkmates_given=checkmates_given,
        checkmates_received=checkmates_received,
        blunder_losses=blunder_losses,
        clean_losses=clean_losses,
        never_blunder_resign=never_blunder_resign,
        suspicious_score=min(1.0, suspicious_score),
    )


# ============================================
# 3. Critical Moment Accuracy
# ============================================

@dataclass
class CriticalMomentAnalysis:
    """Analysis of accuracy in critical positions."""
    total_critical_moments: int
    critical_accuracy: float  # Accuracy in ±1 pawn positions
    non_critical_accuracy: float  # Accuracy in clear positions
    accuracy_gap: float  # critical - non_critical (negative = suspicious)
    suspicious_score: float


def analyze_critical_moments(
    moves_data: List[Dict],
    critical_threshold: float = 100,  # centipawns - position is ±1 pawn
) -> CriticalMomentAnalysis:
    """
    Analyze accuracy specifically in critical positions.
    
    Suspicious: High accuracy in critical moments vs normal positions
    Normal: Lower accuracy in critical moments (pressure)
    """
    if not moves_data:
        return CriticalMomentAnalysis(0, 0.0, 0.0, 0.0, 0.0)
    
    critical_accuracies = []
    non_critical_accuracies = []
    
    for move in moves_data:
        eval_before = abs(move.get("eval_before", 0))
        accuracy = move.get("accuracy", 0.5)
        
        if eval_before <= critical_threshold:
            critical_accuracies.append(accuracy)
        else:
            non_critical_accuracies.append(accuracy)
    
    critical_accuracy = mean(critical_accuracies) if critical_accuracies else 0.5
    non_critical_accuracy = mean(non_critical_accuracies) if non_critical_accuracies else 0.5
    
    accuracy_gap = critical_accuracy - non_critical_accuracy
    
    # Suspicious: Performs BETTER in critical moments
    # Normal: Performs worse under pressure
    if accuracy_gap > 0.1:
        suspicious_score = min(1.0, accuracy_gap * 2)
    else:
        suspicious_score = 0.0
    
    return CriticalMomentAnalysis(
        total_critical_moments=len(critical_accuracies),
        critical_accuracy=critical_accuracy,
        non_critical_accuracy=non_critical_accuracy,
        accuracy_gap=accuracy_gap,
        suspicious_score=suspicious_score,
    )


# ============================================
# 4. Time Usage Distribution
# ============================================

@dataclass
class TimeDistributionAnalysis:
    """Statistical analysis of move time distribution."""
    total_moves: int
    mean_time: float
    median_time: float
    std_dev: float
    coefficient_of_variation: float  # std/mean - low = suspicious
    bimodal_score: float  # 0-1, high = bimodal distribution (suspicious)
    flat_distribution: bool
    suspicious_score: float


def analyze_time_distribution(
    move_times: List[float],
    min_moves: int = 20,
) -> TimeDistributionAnalysis:
    """
    Analyze the statistical distribution of move times.
    
    Suspicious: Flat distribution, bimodal patterns, low variance
    Normal: Bell curve with natural variance
    """
    if len(move_times) < min_moves:
        return TimeDistributionAnalysis(
            len(move_times), 0.0, 0.0, 0.0, 0.0, 0.0, False, 0.0
        )
    
    mean_time = mean(move_times)
    median_time = median(move_times)
    std_dev = stdev(move_times) if len(move_times) > 1 else 0
    
    # Coefficient of variation (normalized stddev)
    cv = std_dev / mean_time if mean_time > 0 else 0
    
    # Check for bimodal distribution
    # Split times into fast (<5s) and slow (>10s)
    fast_moves = sum(1 for t in move_times if t < 3)
    slow_moves = sum(1 for t in move_times if t > 10)
    mid_moves = len(move_times) - fast_moves - slow_moves
    
    # Bimodal if many fast AND slow, few in middle
    if len(move_times) > 0:
        fast_ratio = fast_moves / len(move_times)
        slow_ratio = slow_moves / len(move_times)
        mid_ratio = mid_moves / len(move_times)
        
        # Bimodal: high fast + high slow + low middle
        bimodal_score = (fast_ratio + slow_ratio) * (1 - mid_ratio)
    else:
        bimodal_score = 0.0
    
    # Flat distribution: low CV
    flat_distribution = cv < 0.3
    
    # Calculate suspicion
    cv_suspicion = max(0, (0.5 - cv)) / 0.5 if cv < 0.5 else 0
    
    suspicious_score = (
        cv_suspicion * 0.5 +
        bimodal_score * 0.3 +
        (0.2 if flat_distribution else 0)
    )
    
    return TimeDistributionAnalysis(
        total_moves=len(move_times),
        mean_time=mean_time,
        median_time=median_time,
        std_dev=std_dev,
        coefficient_of_variation=cv,
        bimodal_score=bimodal_score,
        flat_distribution=flat_distribution,
        suspicious_score=min(1.0, suspicious_score),
    )


# ============================================
# 5. Opponent Correlation Analysis
# ============================================

@dataclass
class OpponentCorrelationAnalysis:
    """Analysis of performance vs opponent strength."""
    games_analyzed: int
    avg_opponent_rating: int
    performance_vs_weaker: float  # Accuracy vs weaker opponents
    performance_vs_stronger: float  # Accuracy vs stronger opponents
    rises_to_occasion: bool  # Plays better vs stronger = suspicious
    correlation_coefficient: float
    suspicious_score: float


def analyze_opponent_correlation(
    games_data: List[Dict],
    player_rating: int = 1500,
) -> OpponentCorrelationAnalysis:
    """
    Analyze if performance correlates with opponent strength.
    
    Suspicious: Playing better against stronger opponents
    Normal: Consistent or slightly worse vs stronger opponents
    """
    if not games_data:
        return OpponentCorrelationAnalysis(0, 0, 0.0, 0.0, False, 0.0, 0.0)
    
    weaker_accuracies = []
    stronger_accuracies = []
    opponent_ratings = []
    
    for game in games_data:
        opp_rating = game.get("opponent_rating", player_rating)
        accuracy = game.get("player_accuracy", 0.5)
        opponent_ratings.append(opp_rating)
        
        if opp_rating < player_rating - 100:
            weaker_accuracies.append(accuracy)
        elif opp_rating > player_rating + 100:
            stronger_accuracies.append(accuracy)
    
    avg_opp_rating = int(mean(opponent_ratings)) if opponent_ratings else player_rating
    perf_vs_weaker = mean(weaker_accuracies) if weaker_accuracies else 0.5
    perf_vs_stronger = mean(stronger_accuracies) if stronger_accuracies else 0.5
    
    # Rising to the occasion = suspicious
    rises_to_occasion = perf_vs_stronger > perf_vs_weaker + 0.05
    
    # Simple correlation (performance gap)
    correlation = perf_vs_stronger - perf_vs_weaker
    
    # Suspicious if playing better vs stronger
    if correlation > 0.1:
        suspicious_score = min(1.0, correlation * 2)
    else:
        suspicious_score = 0.0
    
    return OpponentCorrelationAnalysis(
        games_analyzed=len(games_data),
        avg_opponent_rating=avg_opp_rating,
        performance_vs_weaker=perf_vs_weaker,
        performance_vs_stronger=perf_vs_stronger,
        rises_to_occasion=rises_to_occasion,
        correlation_coefficient=correlation,
        suspicious_score=suspicious_score,
    )


# ============================================
# 6. Session Analysis
# ============================================

@dataclass
class SessionAnalysis:
    """Analysis of performance within playing sessions."""
    total_sessions: int
    avg_session_length: int  # Games per session
    avg_performance_decline: float  # Accuracy drop over session
    never_tires: bool  # No decline = suspicious
    session_variance: float  # Variance in decline across sessions
    suspicious_score: float


def analyze_sessions(
    games_data: List[Dict],
    session_gap_minutes: int = 30,
) -> SessionAnalysis:
    """
    Analyze performance within playing sessions.
    
    Suspicious: No performance decline over long sessions
    Normal: Natural fatigue and accuracy decline
    """
    if not games_data or len(games_data) < 5:
        return SessionAnalysis(0, 0, 0.0, False, 0.0, 0.0)
    
    # Sort by timestamp
    sorted_games = sorted(games_data, key=lambda g: g.get("timestamp", 0))
    
    sessions = []
    current_session = []
    last_time = 0
    
    for game in sorted_games:
        game_time = game.get("timestamp", 0)
        
        if current_session and (game_time - last_time) > session_gap_minutes * 60:
            # New session
            sessions.append(current_session)
            current_session = []
        
        current_session.append(game)
        last_time = game_time
    
    if current_session:
        sessions.append(current_session)
    
    # Analyze performance decline in each session
    session_declines = []
    
    for session in sessions:
        if len(session) >= 3:
            first_half = session[:len(session)//2]
            second_half = session[len(session)//2:]
            
            first_acc = mean([g.get("player_accuracy", 0.5) for g in first_half])
            second_acc = mean([g.get("player_accuracy", 0.5) for g in second_half])
            
            decline = first_acc - second_acc
            session_declines.append(decline)
    
    if not session_declines:
        return SessionAnalysis(
            total_sessions=len(sessions),
            avg_session_length=int(mean([len(s) for s in sessions])) if sessions else 0,
            avg_performance_decline=0.0,
            never_tires=False,
            session_variance=0.0,
            suspicious_score=0.0,
        )
    
    avg_decline = mean(session_declines)
    variance = stdev(session_declines) if len(session_declines) > 1 else 0
    
    # Never tiring is suspicious
    never_tires = avg_decline < 0.01 and len(session_declines) >= 3
    
    # Suspicious if no fatigue
    if never_tires:
        suspicious_score = 0.6
    elif avg_decline < 0.02:
        suspicious_score = 0.3
    else:
        suspicious_score = 0.0
    
    return SessionAnalysis(
        total_sessions=len(sessions),
        avg_session_length=int(mean([len(s) for s in sessions])),
        avg_performance_decline=avg_decline,
        never_tires=never_tires,
        session_variance=variance,
        suspicious_score=suspicious_score,
    )


# ============================================
# Combined Analysis Function
# ============================================

@dataclass
class AdvancedSignals:
    """All advanced detection signals combined."""
    opening: OpeningAnalysis
    resignation: ResignationAnalysis
    critical_moment: CriticalMomentAnalysis
    time_distribution: TimeDistributionAnalysis
    opponent_correlation: OpponentCorrelationAnalysis
    session: SessionAnalysis
    
    def get_suspicion_scores(self) -> Dict[str, float]:
        """Get all suspicion scores as a dict."""
        return {
            "opening_repertoire": self.opening.suspicious_score,
            "resignation_pattern": self.resignation.suspicious_score,
            "critical_moment": self.critical_moment.suspicious_score,
            "time_distribution": self.time_distribution.suspicious_score,
            "opponent_correlation": self.opponent_correlation.suspicious_score,
            "session_fatigue": self.session.suspicious_score,
        }
