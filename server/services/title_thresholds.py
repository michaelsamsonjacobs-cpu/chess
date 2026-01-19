"""Title-based thresholds for chess cheat detection.

Based on research from Chess.com and Lichess data:
- Super-GM typically has CPL 5-10 in classical, 88%+ accuracy in blitz
- GM typically has CPL 10-15 in classical, 84%+ accuracy in blitz
- Time controls significantly affect expected metrics
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TitleThresholds:
    """Expected metrics for a given title and time control."""
    min_cpl: float  # Minimum expected CPL (anything lower is suspicious)
    max_cpl: float  # Maximum normal CPL
    min_accuracy: float  # Minimum expected accuracy
    engine_agreement_suspicious: float  # Threshold for suspicious engine agreement
    engine_agreement_very_suspicious: float  # Threshold for very suspicious
    top2_agreement_suspicious: float  # Top-2 engine moves threshold


# Thresholds by title and time control
# Format: (min_cpl, max_cpl, min_accuracy, eng_susp, eng_very_susp, top2_susp)
TITLE_THRESHOLDS: Dict[str, Dict[str, Tuple[float, ...]]] = {
    # Super Grandmasters (2700+)
    "SGM": {
        "classical": (3, 12, 0.95, 0.88, 0.94, 0.92),
        "rapid": (5, 18, 0.92, 0.85, 0.92, 0.90),
        "blitz": (10, 28, 0.88, 0.82, 0.90, 0.88),
        "bullet": (15, 45, 0.80, 0.78, 0.88, 0.85),
    },
    # Grandmasters (2500-2700)
    "GM": {
        "classical": (5, 18, 0.92, 0.85, 0.92, 0.90),
        "rapid": (10, 22, 0.88, 0.82, 0.90, 0.88),
        "blitz": (15, 32, 0.84, 0.80, 0.88, 0.85),
        "bullet": (20, 55, 0.75, 0.75, 0.85, 0.82),
    },
    # International Masters (2400-2500)
    "IM": {
        "classical": (10, 22, 0.88, 0.80, 0.88, 0.86),
        "rapid": (15, 28, 0.85, 0.78, 0.86, 0.84),
        "blitz": (20, 38, 0.80, 0.75, 0.85, 0.82),
        "bullet": (25, 60, 0.70, 0.72, 0.82, 0.80),
    },
    # Woman Grandmaster
    "WGM": {
        "classical": (12, 25, 0.86, 0.78, 0.86, 0.84),
        "rapid": (18, 30, 0.82, 0.75, 0.84, 0.82),
        "blitz": (22, 40, 0.78, 0.72, 0.82, 0.80),
        "bullet": (28, 62, 0.68, 0.70, 0.80, 0.78),
    },
    # FIDE Masters (2300-2400)
    "FM": {
        "classical": (15, 28, 0.85, 0.76, 0.85, 0.83),
        "rapid": (20, 32, 0.82, 0.73, 0.83, 0.80),
        "blitz": (25, 42, 0.78, 0.70, 0.80, 0.78),
        "bullet": (30, 65, 0.68, 0.68, 0.78, 0.75),
    },
    # Woman International Master
    "WIM": {
        "classical": (18, 30, 0.82, 0.73, 0.83, 0.80),
        "rapid": (22, 35, 0.78, 0.70, 0.80, 0.78),
        "blitz": (28, 45, 0.74, 0.68, 0.78, 0.75),
        "bullet": (32, 68, 0.65, 0.65, 0.76, 0.73),
    },
    # Candidate Master (2200-2300)
    "CM": {
        "classical": (20, 32, 0.82, 0.72, 0.82, 0.80),
        "rapid": (25, 38, 0.78, 0.70, 0.80, 0.77),
        "blitz": (30, 48, 0.74, 0.67, 0.77, 0.75),
        "bullet": (35, 70, 0.64, 0.64, 0.74, 0.72),
    },
    # Woman FIDE Master
    "WFM": {
        "classical": (22, 35, 0.80, 0.70, 0.80, 0.78),
        "rapid": (28, 40, 0.75, 0.68, 0.78, 0.75),
        "blitz": (32, 50, 0.71, 0.65, 0.75, 0.73),
        "bullet": (38, 72, 0.62, 0.62, 0.73, 0.70),
    },
    # National Master (US ~2200)
    "NM": {
        "classical": (22, 35, 0.80, 0.70, 0.80, 0.78),
        "rapid": (28, 40, 0.76, 0.68, 0.78, 0.75),
        "blitz": (32, 50, 0.72, 0.65, 0.75, 0.73),
        "bullet": (38, 72, 0.63, 0.62, 0.73, 0.70),
    },
    # Woman Candidate Master
    "WCM": {
        "classical": (25, 38, 0.78, 0.68, 0.78, 0.75),
        "rapid": (30, 42, 0.73, 0.65, 0.75, 0.73),
        "blitz": (35, 52, 0.69, 0.62, 0.73, 0.70),
        "bullet": (40, 75, 0.60, 0.60, 0.70, 0.68),
    },
    # Untitled players
    "UNTITLED": {
        "classical": (30, 50, 0.75, 0.65, 0.75, 0.72),
        "rapid": (35, 55, 0.70, 0.62, 0.72, 0.70),
        "blitz": (40, 60, 0.65, 0.58, 0.70, 0.68),
        "bullet": (50, 80, 0.55, 0.55, 0.68, 0.65),
    },
}

# Title display names and skill descriptions
TITLE_INFO: Dict[str, Dict[str, str]] = {
    "SGM": {"name": "Super Grandmaster", "level": "Elite (2700+)"},
    "GM": {"name": "Grandmaster", "level": "World Class (2500-2700)"},
    "IM": {"name": "International Master", "level": "Expert (2400-2500)"},
    "WGM": {"name": "Woman Grandmaster", "level": "Expert"},
    "FM": {"name": "FIDE Master", "level": "Strong (2300-2400)"},
    "WIM": {"name": "Woman International Master", "level": "Strong"},
    "CM": {"name": "Candidate Master", "level": "Advanced (2200-2300)"},
    "WFM": {"name": "Woman FIDE Master", "level": "Advanced"},
    "NM": {"name": "National Master", "level": "Advanced (~2200)"},
    "WCM": {"name": "Woman Candidate Master", "level": "Intermediate"},
    "UNTITLED": {"name": "Untitled", "level": "Various"},
}


def get_thresholds(title: Optional[str], time_control: str = "blitz") -> TitleThresholds:
    """Get expected thresholds for a title and time control.
    
    Args:
        title: Player title (GM, IM, FM, CM, NM, WGM, WIM, WFM, WCM, or None)
        time_control: One of 'classical', 'rapid', 'blitz', 'bullet'
    
    Returns:
        TitleThresholds dataclass with expected metrics
    """
    # Normalize title
    normalized_title = "UNTITLED"
    if title:
        title_upper = title.upper()
        # Handle super-GM detection (can check rating too)
        if title_upper in TITLE_THRESHOLDS:
            normalized_title = title_upper
    
    # Normalize time control
    tc_lower = time_control.lower()
    if tc_lower not in ["classical", "rapid", "blitz", "bullet"]:
        # Map common time controls
        if "bullet" in tc_lower or "1+0" in tc_lower or "2+1" in tc_lower:
            tc_lower = "bullet"
        elif "blitz" in tc_lower or "3+0" in tc_lower or "5+0" in tc_lower:
            tc_lower = "blitz"
        elif "rapid" in tc_lower or "10+" in tc_lower or "15+" in tc_lower:
            tc_lower = "rapid"
        else:
            tc_lower = "blitz"  # Default
    
    thresholds = TITLE_THRESHOLDS[normalized_title][tc_lower]
    
    return TitleThresholds(
        min_cpl=thresholds[0],
        max_cpl=thresholds[1],
        min_accuracy=thresholds[2],
        engine_agreement_suspicious=thresholds[3],
        engine_agreement_very_suspicious=thresholds[4],
        top2_agreement_suspicious=thresholds[5],
    )


def assess_suspicion_with_context(
    metrics: Dict[str, float],
    title: Optional[str],
    time_control: str = "blitz"
) -> Dict[str, Any]:
    """Assess player metrics against title-adjusted expectations.
    
    Returns dict with:
        - overall_assessment: 'normal', 'elevated', 'suspicious', 'very_suspicious'
        - flags: List of specific concerns
        - context: Human-readable explanation
        - expected: The thresholds used
    """
    thresholds = get_thresholds(title, time_control)
    title_info = TITLE_INFO.get(title.upper() if title else "UNTITLED", TITLE_INFO["UNTITLED"])
    
    flags = []
    
    # Check engine agreement
    eng_agree = metrics.get("engine_agreement", 0)
    if eng_agree > thresholds.engine_agreement_very_suspicious:
        flags.append({
            "metric": "engine_agreement",
            "value": eng_agree,
            "threshold": thresholds.engine_agreement_very_suspicious,
            "severity": "very_suspicious",
            "message": f"Engine agreement {eng_agree:.1%} exceeds {thresholds.engine_agreement_very_suspicious:.1%} threshold for {title_info['name']}"
        })
    elif eng_agree > thresholds.engine_agreement_suspicious:
        flags.append({
            "metric": "engine_agreement",
            "value": eng_agree,
            "threshold": thresholds.engine_agreement_suspicious,
            "severity": "suspicious",
            "message": f"Engine agreement {eng_agree:.1%} elevated for {title_info['name']} in {time_control}"
        })
    
    # Check top-2 agreement
    top2 = metrics.get("top2_engine_agreement", 0)
    if top2 > thresholds.top2_agreement_suspicious:
        flags.append({
            "metric": "top2_engine_agreement",
            "value": top2,
            "threshold": thresholds.top2_agreement_suspicious,
            "severity": "suspicious" if top2 < 0.95 else "very_suspicious",
            "message": f"Top-2 engine agreement {top2:.1%} is high for {time_control}"
        })
    
    # Check CPL (if too low, suspicious)
    cpl = metrics.get("average_centipawn_loss", 50)
    if cpl < thresholds.min_cpl:
        flags.append({
            "metric": "centipawn_loss",
            "value": cpl,
            "threshold": thresholds.min_cpl,
            "severity": "suspicious",
            "message": f"CPL {cpl:.1f} is unusually low for {title_info['name']} in {time_control} (expected >{thresholds.min_cpl})"
        })
    
    # Check timing score
    timing = metrics.get("timing_score", 0)
    if timing > 0.4:
        flags.append({
            "metric": "timing_score",
            "value": timing,
            "threshold": 0.4,
            "severity": "very_suspicious" if timing > 0.6 else "suspicious",
            "message": f"Timing patterns score {timing:.2f} indicates non-human timing"
        })
    
    # Overall assessment
    very_sus_count = sum(1 for f in flags if f["severity"] == "very_suspicious")
    sus_count = sum(1 for f in flags if f["severity"] == "suspicious")
    
    if very_sus_count >= 2:
        overall = "very_suspicious"
    elif very_sus_count >= 1 or sus_count >= 2:
        overall = "suspicious"
    elif sus_count >= 1:
        overall = "elevated"
    else:
        overall = "normal"
    
    # Generate context
    context = f"As a {title_info['name']} ({title_info['level']}), expected metrics in {time_control}: "
    context += f"engine agreement <{thresholds.engine_agreement_suspicious:.0%}, "
    context += f"CPL {thresholds.min_cpl}-{thresholds.max_cpl}. "
    
    if flags:
        context += f"Found {len(flags)} metric(s) outside expected range."
    else:
        context += "All metrics within expected range for this skill level."
    
    return {
        "overall_assessment": overall,
        "flags": flags,
        "context": context,
        "expected": {
            "title": title_info["name"],
            "level": title_info["level"],
            "time_control": time_control,
            "engine_agreement_threshold": thresholds.engine_agreement_suspicious,
            "top2_threshold": thresholds.top2_agreement_suspicious,
            "cpl_range": (thresholds.min_cpl, thresholds.max_cpl),
        }
    }
