"""
Mouse/Input Telemetry Analysis (Placeholder)

Placeholder service for analyzing mouse movement and input patterns.
This will detect suspicious patterns when telemetry data is available.

Suspicious patterns:
- Straight-line mouse movements (bot behavior)
- Instant/zero-delay moves
- Perfect click accuracy on squares
- Lack of hesitation or exploration
- Consistent movement speed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

LOGGER = logging.getLogger(__name__)


@dataclass
class ClickEvent:
    """A single click event during a game."""
    timestamp: float  # Unix timestamp
    x: int  # Screen X coordinate
    y: int  # Screen Y coordinate
    square: Optional[str]  # Chess square if on board (e.g., "e4")
    event_type: str  # "mousedown", "mouseup", "click"


@dataclass
class MousePath:
    """A mouse movement path between clicks."""
    start_time: float
    end_time: float
    points: List[Dict]  # {"x": int, "y": int, "t": float}
    straightness: float  # 0 = curved, 1 = perfectly straight
    speed_variance: float  # Low variance = suspicious


@dataclass  
class TelemetryAnalysis:
    """Result of telemetry analysis."""
    total_moves: int
    avg_move_time: float
    
    # Suspicious indicators
    straight_line_ratio: float  # Ratio of straight-line movements
    instant_move_count: int  # Moves with < 100ms
    speed_consistency: float  # How consistent mouse speed is (high = suspicious)
    
    # Overall score
    suspicion_score: float  # 0-1, higher = more suspicious
    flags: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "total_moves": self.total_moves,
            "avg_move_time": self.avg_move_time,
            "straight_line_ratio": self.straight_line_ratio,
            "instant_move_count": self.instant_move_count,
            "speed_consistency": self.speed_consistency,
            "suspicion_score": self.suspicion_score,
            "flags": self.flags,
        }


def analyze_telemetry(
    events: List[ClickEvent],
    paths: List[MousePath],
) -> TelemetryAnalysis:
    """
    Analyze mouse telemetry for suspicious patterns.
    
    NOTE: This is a placeholder implementation.
    Returns neutral scores until real telemetry data is available.
    """
    
    if not events or not paths:
        # No data available - return neutral
        return TelemetryAnalysis(
            total_moves=0,
            avg_move_time=0.0,
            straight_line_ratio=0.0,
            instant_move_count=0,
            speed_consistency=0.0,
            suspicion_score=0.0,
            flags=["no_telemetry_data"],
        )
    
    # Calculate metrics
    total_moves = len(events) // 2  # Two clicks per move
    
    # Average time between moves
    if len(events) >= 2:
        times = [e.timestamp for e in events]
        deltas = [times[i+1] - times[i] for i in range(len(times)-1)]
        avg_move_time = sum(deltas) / len(deltas) if deltas else 0
    else:
        avg_move_time = 0
    
    # Count instant moves (< 100ms)
    instant_count = sum(1 for d in deltas if d < 0.1) if deltas else 0
    
    # Calculate straight line ratio
    if paths:
        straight_count = sum(1 for p in paths if p.straightness > 0.95)
        straight_ratio = straight_count / len(paths)
    else:
        straight_ratio = 0.0
    
    # Calculate speed consistency (low variance = suspicious)
    if paths:
        speeds = [len(p.points) / max(0.001, p.end_time - p.start_time) for p in paths]
        if speeds:
            avg_speed = sum(speeds) / len(speeds)
            variance = sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)
            # Normalize: high variance = human, low variance = bot
            speed_consistency = 1.0 / (1.0 + variance / 100)
        else:
            speed_consistency = 0.0
    else:
        speed_consistency = 0.0
    
    # Build flags
    flags = []
    if straight_ratio > 0.5:
        flags.append("high_straight_line_ratio")
    if instant_count > 5:
        flags.append("many_instant_moves")
    if speed_consistency > 0.8:
        flags.append("consistent_speed")
    
    # Calculate overall suspicion
    suspicion = (
        straight_ratio * 0.3 +
        min(1.0, instant_count / 10) * 0.3 +
        speed_consistency * 0.4
    )
    
    return TelemetryAnalysis(
        total_moves=total_moves,
        avg_move_time=avg_move_time,
        straight_line_ratio=straight_ratio,
        instant_move_count=instant_count,
        speed_consistency=speed_consistency,
        suspicion_score=suspicion,
        flags=flags,
    )


def get_telemetry_score_for_detection() -> float:
    """
    Get telemetry suspicion score for use in ensemble detection.
    
    Returns 0.0 (neutral) until telemetry data collection is implemented.
    """
    LOGGER.info("Telemetry analysis called - no data available (placeholder)")
    return 0.0  # Neutral - doesn't affect ensemble score


# ============================================
# Future: API endpoint for receiving telemetry
# ============================================

def parse_telemetry_payload(payload: Dict) -> tuple:
    """
    Parse incoming telemetry data from browser extension.
    
    Expected format:
    {
        "game_id": "abc123",
        "events": [
            {"t": 1234567890.123, "x": 100, "y": 200, "type": "click", "square": "e4"}
        ],
        "paths": [
            {"start": 0.0, "end": 0.5, "points": [{"x": 0, "y": 0, "t": 0.0}]}
        ]
    }
    """
    events = []
    for e in payload.get("events", []):
        events.append(ClickEvent(
            timestamp=e.get("t", 0),
            x=e.get("x", 0),
            y=e.get("y", 0),
            square=e.get("square"),
            event_type=e.get("type", "click"),
        ))
    
    paths = []
    for p in payload.get("paths", []):
        paths.append(MousePath(
            start_time=p.get("start", 0),
            end_time=p.get("end", 0),
            points=p.get("points", []),
            straightness=p.get("straightness", 0),
            speed_variance=p.get("speed_variance", 0),
        ))
    
    return events, paths
