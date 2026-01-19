"""Ensemble Suspicion Score Calculator.

Combines all detection signals into a single weighted score:
1. Engine agreement (excluding book moves)
2. Timing anomalies
3. Streak improbability
4. Scramble toggle detection
5. Complexity-accuracy correlation
6. Opening deviation patterns

The ensemble approach is harder to game because cheaters
would need to beat ALL detection methods simultaneously.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from statistics import mean

LOGGER = logging.getLogger(__name__)


@dataclass
class DetectionSignals:
    """All detection signals for a player/game."""
    # Core engine analysis
    engine_agreement: float = 0.0  # 0-1, raw engine agreement
    adjusted_engine_agreement: float = 0.0  # Excluding book moves
    moves_in_book: int = 0
    
    # Timing analysis
    timing_suspicion: float = 0.0  # 0-1
    scramble_toggle_score: float = 0.0  # 0-1
    uniform_timing_score: float = 0.0  # 0-1
    
    # Streak analysis (player-level)
    streak_improbability_score: float = 0.0  # 0-1
    longest_win_streak: int = 0
    streak_density: float = 0.0 # 0-1, from Windowed Analysis (percentage of high accuracy games in window)
    
    # Complexity-accuracy correlation
    complexity_accuracy_corr: Optional[float] = None  # -1 to 1
    avg_complexity: float = 0.0
    
    # Performance vs rating
    performance_rating: int = 0
    actual_rating: int = 0
    rating_delta: int = 0  # performance - actual
    
    # ML-based human likelihood (0=bot-like, 1=human-like)
    human_likelihood: float = 1.0  # Default to human-like
    non_obvious_engine_moves: int = 0
    
    # Known cheater database flag
    is_known_cheater: bool = False
    cheater_source: Optional[str] = None
    
    # Historical anomaly detection
    history_anomaly_detected: bool = False
    accuracy_trend: Optional[str] = None  # "improving", "stable", "suspicious_jump"
    accuracy_change: float = 0.0  # Recent change in accuracy
    
    # ADVANCED: Opening repertoire analysis
    opening_repertoire_score: float = 0.0  # 0-1, variety + accuracy = suspicious
    unique_openings_count: int = 0
    
    # ADVANCED: Resignation pattern analysis
    resignation_pattern_score: float = 0.0  # 0-1, never blunder-resigning = suspicious
    never_blunder_resign: bool = False
    
    # ADVANCED: Critical moment accuracy (Sniper Detection)
    critical_moment_score: float = 0.0  # 0-1, better in critical = suspicious
    critical_vs_normal_gap: float = 0.0 # Sniper Index
    critical_moves_correct: int = 0
    critical_moves_total: int = 0
    normal_moves_correct: int = 0
    normal_moves_total: int = 0
    
    # ADVANCED: Time usage distribution
    time_distribution_score: float = 0.0  # 0-1, flat/bimodal = suspicious
    time_cv: float = 0.0  # Coefficient of variation
    
    # ADVANCED: Opponent correlation
    opponent_correlation_score: float = 0.0  # 0-1, better vs stronger = suspicious
    rises_to_occasion: bool = False
    
    # ADVANCED: Session fatigue analysis
    session_fatigue_score: float = 0.0  # 0-1, never tires = suspicious
    never_tires: bool = False
    
    # Meta signals
    games_analyzed: int = 0
    flagged_games: int = 0
    high_accuracy_games_count: int = 0  # Games with >95% accuracy


@dataclass
class EnsembleResult:
    """Final ensemble suspicion score with breakdown."""
    ensemble_score: float  # 0-100 final score
    risk_level: str  # "low", "medium", "high", "critical"
    confidence: float  # 0-1 confidence in the score
    
    # [Truncated dataclass fields for brevity, they remain same]
    confidence_low: float  # Lower bound of estimate  
    confidence_high: float  # Upper bound of estimate
    uncertainty_level: str  # "low", "medium", "high"
    
    # Component scores (weighted) - 15 signals total
    engine_component: float
    timing_component: float
    streak_component: float
    scramble_component: float
    complexity_component: float
    rating_component: float
    human_ml_component: float
    known_cheater_component: float
    history_component: float
    # Advanced components
    opening_component: float
    resignation_component: float
    critical_moment_component: float
    time_distribution_component: float
    opponent_corr_component: float
    session_component: float
    
    # Flags
    flags: List[str]  # Human-readable flags
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ensemble_score": round(self.ensemble_score, 1),
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 3),
            "confidence_low": round(self.confidence_low, 1),
            "confidence_high": round(self.confidence_high, 1),
            "uncertainty_level": self.uncertainty_level,
            "components": {
                "engine": round(self.engine_component, 3),
                "timing": round(self.timing_component, 3),
                "streak": round(self.streak_component, 3),
                "scramble": round(self.scramble_component, 3),
                "complexity": round(self.complexity_component, 3),
                "rating": round(self.rating_component, 3),
                "human_ml": round(self.human_ml_component, 3),
                "known_cheater": round(self.known_cheater_component, 3),
                "history": round(self.history_component, 3),
                "opening": round(self.opening_component, 3),
                "resignation": round(self.resignation_component, 3),
                "critical_moment": round(self.critical_moment_component, 3),
                "time_distribution": round(self.time_distribution_component, 3),
                "opponent_corr": round(self.opponent_corr_component, 3),
                "session": round(self.session_component, 3),
            },
            "flags": self.flags,
        }



# Ensemble weights - sum to 1.0
# 15 total signals for comprehensive cheat detection
# CALIBRATED 2025-12-20 based on 24 titled cheater dataset
WEIGHTS = {
    # Core signals (50%)
    "engine": 0.15,           # Engine agreement (adjusted for book)
    "timing": 0.10,           # Timing anomalies
    "streak": 0.06,           # Improbable streaks
    "scramble": 0.06,         # Time scramble toggle
    "complexity": 0.06,       # Complexity-accuracy correlation
    "rating": 0.07,           # Performance vs actual rating
    
    # ML & Database signals (18%)
    "human_ml": 0.08,         # ML human likelihood (inverted)
    "known_cheater": 0.06,    # Known banned player
    "history": 0.04,          # Historical anomaly
    
    # Advanced signals (32%)
    "opening": 0.05,          # Opening repertoire variety + accuracy
    "resignation": 0.05,      # Resignation patterns
    "critical_moment": 0.07,  # Critical position accuracy
    "time_distribution": 0.05, # Time usage statistics
    "opponent_corr": 0.05,    # Performance vs opponent strength
    "session": 0.05,          # Session fatigue patterns
}


def calculate_ensemble_score(signals: DetectionSignals) -> EnsembleResult:
    """
    Calculate weighted ensemble suspicion score.
    
    Args:
        signals: All detection signals for a player/game
        
    Returns:
        EnsembleResult with final score and breakdown
    """
    flags = []
    
    # 1. Engine Component (higher = more suspicious)
    # Use adjusted agreement excluding book moves
    # High agreement (>95%) = suspicious, <70% = normal
    # CALIBRATION: Tigran Petrosian had 123 games > 95%
    engine_raw = signals.adjusted_engine_agreement
    if engine_raw > 0.95:
        engine_component = 1.0
        flags.append("🚨 Very high engine agreement (>95%)")
    elif engine_raw > 0.90:
        engine_component = 0.8
        flags.append("⚠️ High engine agreement (>90%)")
    elif engine_raw > 0.85:
        engine_component = 0.5
    elif engine_raw > 0.75:
        engine_component = 0.2
    else:
        engine_component = 0.0
    
    # Check for volume of high accuracy games (Tigran pattern)
    if signals.games_analyzed > 5:
        high_acc_ratio = signals.high_accuracy_games_count / signals.games_analyzed
        if signals.high_accuracy_games_count > 10 and high_acc_ratio > 0.1:
            flags.append(f"🚨 Suspect Volume: {signals.high_accuracy_games_count} games with >95% accuracy")
            engine_component = 1.0 # Force max engine score
            
    # 2. Timing Component
    timing_component = signals.timing_suspicion
    if timing_component > 0.7:
        flags.append("⚠️ Suspicious timing patterns")
    
    # 3. Streak Component (Updated V2: Windowed + Imbprobability)
    streak_imp = signals.streak_improbability_score
    streak_dense = signals.streak_density # From windowed analysis
    
    # Combined streak score
    streak_component = max(streak_imp, streak_dense * 3.0) # Density > 30% is critical (0.3 * 3 = 0.9)
    if streak_component > 1.0: streak_component = 1.0
    
    if streak_dense > 0.25:
        flags.append(f"🚨 Suspicious streak density ({streak_dense:.0%} perfect games in window)")
    elif streak_dense > 0.15:
        flags.append(f"⚠️ Elevated streak density ({streak_dense:.0%} perfect games in window)")
    elif streak_imp > 0.6:
        flags.append(f"⚠️ Improbable win streaks (longest: {signals.longest_win_streak})")
    
    # 4. Scramble Toggle Component
    scramble_component = signals.scramble_toggle_score
    if scramble_component > 0.6:
        flags.append("🚨 Engine toggle detected in time scramble")
    
    # 5. Complexity-Accuracy Component
    # Negative correlation (high accuracy on complex positions) = suspicious
    complexity_component = 0.0
    if signals.complexity_accuracy_corr is not None:
        if signals.complexity_accuracy_corr < -0.3:
            complexity_component = 0.8
            flags.append("⚠️ Unusual accuracy-complexity pattern")
        elif signals.complexity_accuracy_corr < -0.1:
            complexity_component = 0.4
        elif signals.complexity_accuracy_corr < 0.1:
            complexity_component = 0.2
        else:
            complexity_component = 0.0
    
    # 6. Rating Delta Component
    # Performance rating >> actual rating = suspicious
    rating_component = 0.0
    if signals.rating_delta > 400:
        rating_component = 1.0
        flags.append(f"🚨 Performance {signals.rating_delta} points above rating")
    elif signals.rating_delta > 300:
        rating_component = 0.7
        flags.append(f"⚠️ Performance {signals.rating_delta} points above rating")
    elif signals.rating_delta > 200:
        rating_component = 0.4
    elif signals.rating_delta > 100:
        rating_component = 0.2
    
    # 7. ML Human Likelihood Component (NEW)
    # Low human likelihood = suspicious (inverted: 0=human, 1=bot-like)
    human_ml_component = 1.0 - signals.human_likelihood
    if human_ml_component > 0.6:
        flags.append(f"🤖 Low human likelihood score ({signals.human_likelihood*100:.0f}%)")
    if signals.non_obvious_engine_moves > 10:
        flags.append(f"⚠️ {signals.non_obvious_engine_moves} non-obvious engine moves")
    
    # 8. Known Cheater Database Component (NEW)
    # Previously banned = major red flag
    known_cheater_component = 1.0 if signals.is_known_cheater else 0.0
    
    # 9. Historical Anomaly Component (NEW)
    # Sudden improvement in accuracy = suspicious
    history_component = 0.0
    if signals.history_anomaly_detected:
        history_component = 0.8
        flags.append(f"📈 Sudden accuracy improvement detected")
    elif signals.accuracy_trend == "suspicious_jump":
        history_component = 0.6
        flags.append(f"⚠️ Unusual accuracy trend (+{signals.accuracy_change*100:.0f}%)")
    elif signals.accuracy_change > 0.15:
        history_component = 0.4
    
    # Calculate weighted ensemble score (9 signals)
    weighted_sum = (
        WEIGHTS["engine"] * engine_component +
        WEIGHTS["timing"] * timing_component +
        WEIGHTS["streak"] * streak_component +
        WEIGHTS["scramble"] * scramble_component +
        WEIGHTS["complexity"] * complexity_component +
        WEIGHTS["rating"] * rating_component +
        WEIGHTS["human_ml"] * human_ml_component +
        WEIGHTS["known_cheater"] * known_cheater_component +
        WEIGHTS["history"] * history_component
    )
    
    # 10. Opening Repertoire Component
    # High variety + high accuracy in openings = suspicious
    opening_component = signals.opening_repertoire_score
    if opening_component > 0.6:
        flags.append(f"📚 Perfect play across {signals.unique_openings_count} different openings")
    
    # 11. Resignation Pattern Component
    # Never losing to blunders = suspicious
    resignation_component = signals.resignation_pattern_score
    if signals.never_blunder_resign:
        flags.append("🏳️ Never loses to blunders (always resigns cleanly)")
    
    # 12. Critical Moment Component (Sniper Detection V2)
    # V2 CALIBRATION: Super GMs (Tang) can hit +31% gap (12/12 critical).
    # Raised thresholds to avoid false positive "Snipers" in top-tier speed chess.
    gap = signals.critical_vs_normal_gap
    if gap > 0.5:
        critical_moment_component = 1.0
        flags.append(f"🚨 SNIPER: Massive accuracy gap at critical moments (+{gap:.0%})")
    elif gap > 0.35:
        critical_moment_component = 0.8
        flags.append(f"🚨 Suspicious critical accuracy gap (+{gap:.0%})")
    elif gap > 0.20:
        critical_moment_component = 0.5
        flags.append(f"⚠️ Elevated critical accuracy (+{gap:.0%})")
    else:
        critical_moment_component = 0.0
    
    # 13. Time Distribution Component
    # Flat/bimodal timing = suspicious
    time_distribution_component = signals.time_distribution_score
    if signals.time_cv < 0.3 and signals.time_cv > 0:
        flags.append(f"⏱️ Robotic timing pattern (CV: {signals.time_cv:.2f})")
    
    # 14. Opponent Correlation Component
    # Playing better vs stronger opponents = suspicious
    opponent_corr_component = signals.opponent_correlation_score
    if signals.rises_to_occasion:
        flags.append("📈 Plays better against stronger opponents")
    
    # 15. Session Fatigue Component
    # Never tiring = suspicious
    session_component = signals.session_fatigue_score
    if signals.never_tires:
        flags.append("🔋 No performance decline over long sessions")
    
    # Add advanced signals to weighted sum (15 total)
    weighted_sum += (
        WEIGHTS["opening"] * opening_component +
        WEIGHTS["resignation"] * resignation_component +
        WEIGHTS["critical_moment"] * critical_moment_component +
        WEIGHTS["time_distribution"] * time_distribution_component +
        WEIGHTS["opponent_corr"] * opponent_corr_component +
        WEIGHTS["session"] * session_component
    )
    
    # Convert to 0-100 scale
    ensemble_score = weighted_sum * 100
    
    # FORCE CRITICAL IF KNOWN CHEATER (Database Override)
    if signals.is_known_cheater:
        ensemble_score = max(ensemble_score, 95.0) # Ensure it's critical
        if "🚨 KNOWN CHEATER - Previously banned" not in [f for f in flags if "KNOWN CHEATER" in f]:
             flags.insert(0, f"🚨 KNOWN CHEATER - Previously banned ({signals.cheater_source or 'Database'})")
    
    # FORCE HIGH/CRITICAL IF SUSPECT VOLUME OF HIGH ACCURACY GAMES
    # Based on Tigran Petrosian analysis (123 games > 95%)
    # If a player has many "perfect" games, they are likely cheating even if other signals are subtle
    if any("Suspect Volume" in f for f in flags):
         # If >20% are perfect, it's critical. If >10%, it's high.
         high_acc_ratio = signals.high_accuracy_games_count / max(1, signals.games_analyzed)
         if high_acc_ratio > 0.2:
             ensemble_score = max(ensemble_score, 85.0) # Critical
         else:
             ensemble_score = max(ensemble_score, 65.0) # High

    # Determine risk level
    if ensemble_score >= 70:
        risk_level = "critical"
    elif ensemble_score >= 50:
        risk_level = "high"
    elif ensemble_score >= 25:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    # Calculate confidence based on data availability
    confidence = _calculate_confidence(signals)
    
    # Calculate confidence interval bounds
    # Wider intervals for lower confidence, narrower for higher confidence
    base_uncertainty = (1 - confidence) * 30  # Max ±30 points at 0 confidence
    
    # Also factor in borderline scores (50% ± 15 is most uncertain)
    borderline_penalty = max(0, 15 - abs(ensemble_score - 50)) * 0.5
    total_uncertainty = base_uncertainty + borderline_penalty
    
    confidence_low = max(0, ensemble_score - total_uncertainty)
    confidence_high = min(100, ensemble_score + total_uncertainty)
    
    # Determine uncertainty level
    if total_uncertainty <= 10:
        uncertainty_level = "low"
    elif total_uncertainty <= 20:
        uncertainty_level = "medium"
    else:
        uncertainty_level = "high"
    
    return EnsembleResult(
        ensemble_score=ensemble_score,
        risk_level=risk_level,
        confidence=confidence,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        uncertainty_level=uncertainty_level,
        engine_component=engine_component,
        timing_component=timing_component,
        streak_component=streak_component,
        scramble_component=scramble_component,
        complexity_component=complexity_component,
        rating_component=rating_component,
        human_ml_component=human_ml_component,
        known_cheater_component=known_cheater_component,
        history_component=history_component,
        opening_component=opening_component,
        resignation_component=resignation_component,
        critical_moment_component=critical_moment_component,
        time_distribution_component=time_distribution_component,
        opponent_corr_component=opponent_corr_component,
        session_component=session_component,
        flags=flags,
    )


def _calculate_confidence(signals: DetectionSignals) -> float:
    """
    Calculate confidence in the ensemble score.
    
    Higher confidence when we have more data.
    """
    confidence_factors = []
    
    # More games = higher confidence
    if signals.games_analyzed >= 50:
        confidence_factors.append(1.0)
    elif signals.games_analyzed >= 20:
        confidence_factors.append(0.8)
    elif signals.games_analyzed >= 10:
        confidence_factors.append(0.6)
    else:
        confidence_factors.append(0.3)
    
    # Have timing data?
    if signals.timing_suspicion > 0:
        confidence_factors.append(0.9)
    else:
        confidence_factors.append(0.5)
    
    # Have complexity data?
    if signals.complexity_accuracy_corr is not None:
        confidence_factors.append(0.9)
    else:
        confidence_factors.append(0.5)
    
    return mean(confidence_factors) if confidence_factors else 0.5


def combine_game_signals(game_signals: List[DetectionSignals]) -> DetectionSignals:
    """
    Combine signals from multiple games into aggregate player signals.
    """
    if not game_signals:
        return DetectionSignals()
    
    # Calculate high accuracy game count (>95%)
    high_acc_count = sum(1 for s in game_signals if s.adjusted_engine_agreement >= 0.95)
    
    return DetectionSignals(
        engine_agreement=mean([s.engine_agreement for s in game_signals]),
        adjusted_engine_agreement=mean([s.adjusted_engine_agreement for s in game_signals]),
        moves_in_book=sum(s.moves_in_book for s in game_signals),
        timing_suspicion=mean([s.timing_suspicion for s in game_signals]),
        scramble_toggle_score=max(s.scramble_toggle_score for s in game_signals),  # Max is most suspicious
        uniform_timing_score=mean([s.uniform_timing_score for s in game_signals]),
        streak_improbability_score=game_signals[0].streak_improbability_score,
        streak_density=game_signals[0].streak_density, # Player-level signal
        longest_win_streak=game_signals[0].longest_win_streak,
        complexity_accuracy_corr=mean([s.complexity_accuracy_corr for s in game_signals if s.complexity_accuracy_corr is not None]) if any(s.complexity_accuracy_corr for s in game_signals) else None,
        avg_complexity=mean([s.avg_complexity for s in game_signals]),
        performance_rating=game_signals[0].performance_rating,
        actual_rating=game_signals[0].actual_rating,
        rating_delta=game_signals[0].rating_delta,
        games_analyzed=len(game_signals),
        flagged_games=sum(1 for s in game_signals if calculate_ensemble_score(s).ensemble_score > 50),
        high_accuracy_games_count=high_acc_count,
        # Detect if marked as known cheater in ANY game (though usually set at player level)
        is_known_cheater=any(s.is_known_cheater for s in game_signals),
        cheater_source=next((s.cheater_source for s in game_signals if s.cheater_source), None),
        
        # Aggregate Critical/Normal stats for Sniper Index recalculation
        critical_moves_correct=sum(s.critical_moves_correct for s in game_signals),
        critical_moves_total=sum(s.critical_moves_total for s in game_signals),
        normal_moves_correct=sum(s.normal_moves_correct for s in game_signals),
        normal_moves_total=sum(s.normal_moves_total for s in game_signals),
        # Recalculate gaps based on aggregated sums
        critical_vs_normal_gap=(
            (sum(s.critical_moves_correct for s in game_signals) / max(1, sum(s.critical_moves_total for s in game_signals))) -
            (sum(s.normal_moves_correct for s in game_signals) / max(1, sum(s.normal_moves_total for s in game_signals)))
        )
    )


def get_risk_color(risk_level: str) -> str:
    """Get CSS color for risk level."""
    colors = {
        "low": "#22c55e",      # Green
        "medium": "#f59e0b",   # Amber
        "high": "#f97316",     # Orange
        "critical": "#ef4444", # Red
    }
    return colors.get(risk_level, "#6b7280")


def get_risk_emoji(risk_level: str) -> str:
    """Get emoji for risk level."""
    emojis = {
        "low": "✅",
        "medium": "⚠️",
        "high": "🔶",
        "critical": "🚨",
    }
    return emojis.get(risk_level, "❓")
