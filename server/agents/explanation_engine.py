"""Explanation Engine for Cheat Detection Reports.

Generates human-readable, plain English explanations for why a player
was flagged as suspicious, using template-based NLG.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
import random

LOGGER = logging.getLogger(__name__)

# Explanation templates keyed by signal type
TEMPLATES = {
    "engine_agreement_high": [
        "{player} matched the engine's top choice {agreement}% of the time across {games} games. This is significantly higher than the expected {expected}% for players rated {rating}. In critical positions where the best move wasn't obvious, they still found it {critical_pct}% of the time.",
        "Analysis of {games} games shows an engine correlation of {agreement}%, which is {sigma} standard deviations above the average for {rating}-rated players. This level of precision is extremely rare in human play.",
        "{player}'s play aligned with the top engine move {agreement}% of the time. For comparison, Grandmasters typically achieve 55-65% accuracy in similar time controls."
    ],
    
    "timing_anomaly": [
        "Move timing patterns are unusual: {player} spent an average of {avg_time} seconds per move with suspiciously low variance (CV={cv}). Complex positions were solved as quickly as simple ones, unlike typical human play.",
        "{player} demonstrated a robotic timing cadence, maintaining a consistent {avg_time}s per move regardless of position complexity. This 'metronome' pattern often indicates external assistance.",
        "The time management profile is highly irregular. {player} avoided natural time trouble even in deeply complex variations, suggesting they were not calculating variations manually."
    ],
    
    "streak_improbability": [
        "Between {start_date} and {end_date}, {player} achieved a win streak that has a probability of {prob} under normal conditions. Even accounting for hot streaks, this performance is a statistical outlier.",
        "{player} won {wins} consecutive games against similarly rated opponents. The statistical likelihood of this streak occurring by chance is less than 1 in {one_in_chance}.",
        "A performance spike of this magnitude ({rating_diff} rating points above average) sustained over {games} games is statistically improbable ({prob} confidence)."
    ],
    
    "critical_accuracy_spike": [
        "In positions where one wrong move loses the game, {player} found the winning move {critical_correct}/{critical_total} times ({pct}%). This 'sniper' pattern—ordinary play punctuated by perfect critical moves—is a hallmark of selective engine use.",
        "{player}'s accuracy jumped to {pct}% specifically in critical moments that decided the game, compared to {normal_pct}% in non-critical positions. This wide gap matches the 'selective toggling' profile.",
        "While playing average moves in opening and endgame phases, {player} played with perfect engine accuracy during complex middlegame complications, finding 12-move tactical sequences instantly."
    ],
    
    "new_account_performance": [
        "This account was created just {days_ago} days ago and has already defeated {titled_opponents} titled players with {accuracy}% accuracy.",
        "Despite being a new account with provisional rating, {player} played with GM-level accuracy ({accuracy}%) immediately upon registration.",
    ],
    
    "platform_ban": [
        "{player} has been officially banned by {platform} for fair play violations. This confirms our detection models' findings.",
        "The {platform} Fair Play team has closed this account for cheating. All games against this opponent should be annulled.",
    ]
}

RISK_LEVEL_DESCRIPTIONS = {
    "CRITICAL": "Critical Risk: Evidence overwhelmingly supports fair play violations.",
    "HIGH": "High Risk: Multiple independent signals indicate non-human assistance.",
    "MODERATE": "Moderate Risk: Suspicious patterns detected warranting further monitoring.",
    "LOW": "Low Risk: Play is consistent with human performance at this rating level."
}


def generate_summary(
    player: str, 
    score: int, 
    risk_level: str, 
    primary_reason: str,
    games_count: int,
    signals: Optional[Dict[str, Any]] = None
) -> str:
    """Generate a comprehensive plain-English summary.
    
    Args:
        player: Username of flagged player
        score: Ensemble suspicion score (0-100)
        risk_level: Risk classification
        primary_reason: Short reason code or text
        games_count: Number of games analyzed
        signals: dictionary of detection signals and metrics
        
    Returns:
        Formatted summary text
    """
    signals = signals or {}
    
    # 1. Intro
    intro = (
        f"ChessGuard has identified **{player}** as **{risk_level}** risk "
        f"({score}/100 suspicion score) based on analysis of {games_count} games."
    )
    
    # 2. Primary Explanation
    explanation = ""
    
    # Check if we have a template for the reason
    template_key = _map_reason_to_key(primary_reason)
    
    if template_key and template_key in TEMPLATES:
        # Format template with available signals
        context = {
            "player": player,
            "games": games_count,
            "rating": signals.get("rating", "their"),
            "agreement": f"{signals.get('engine_agreement', 0):.1f}",
            "expected": f"{signals.get('expected_agreement', 50):.1f}",
            "critical_pct": f"{signals.get('critical_accuracy', 0):.1f}",
            "sigma": f"{signals.get('sigma', 3.0):.1f}",
            "avg_time": f"{signals.get('avg_move_time', 0):.1f}",
            "cv": f"{signals.get('time_cv', 0):.2f}",
            "prob": f"{signals.get('streak_prob', '0.001%')}",
            "platform": signals.get("platform", "the platform"),
            "days_ago": signals.get("account_age_days", 1),
            "accuracy": f"{signals.get('accuracy', 90):.1f}",
        }
        
        # Pick a random variant for variety
        template = random.choice(TEMPLATES[template_key])
        try:
            explanation = template.format(**context)
        except KeyError:
            # Fallback if context missing
            explanation = primary_reason
    else:
        # Use raw reason if no template match
        explanation = primary_reason
        
    # 3. Verdict / Recommendation
    verdict = RISK_LEVEL_DESCRIPTIONS.get(risk_level, "")
    
    return f"{intro}\n\n{explanation}\n\n**Verdict:** {verdict}"


def _map_reason_to_key(reason: str) -> Optional[str]:
    """Map a raw reason string or code to a template key."""
    reason_lower = reason.lower()
    
    if "accuracy" in reason_lower and "critical" in reason_lower:
        return "critical_accuracy_spike"
    if "engine" in reason_lower or "agreement" in reason_lower:
        return "engine_agreement_high"
    if "time" in reason_lower or "timing" in reason_lower:
        return "timing_anomaly"
    if "streak" in reason_lower:
        return "streak_improbability"
    if "ban" in reason_lower or "closed" in reason_lower:
        return "platform_ban"
    if "new" in reason_lower and "account" in reason_lower:
        return "new_account_performance"
        
    return None
