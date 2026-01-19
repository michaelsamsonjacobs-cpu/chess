"""
Historical Player Tracking Service

Tracks player metrics over time to detect sudden improvements
that may indicate the start of cheating behavior.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from server.models.game import PlayerSnapshot, BatchAnalysis


@dataclass
class TrendAnalysis:
    """Result of trend analysis for a player."""
    username: str
    platform: str
    snapshots_count: int
    
    # Current metrics
    current_accuracy: float
    current_engine_agreement: float
    current_rating: Optional[int]
    
    # Historical comparison
    accuracy_change: float  # Percentage point change
    agreement_change: float
    rating_change: Optional[int]
    
    # Trend classification
    trend: str  # "improving", "stable", "declining", "suspicious_jump"
    is_anomaly: bool
    anomaly_reason: Optional[str]
    
    # History for charting
    history: List[Dict]


def record_snapshot(
    db: Session,
    username: str,
    platform: str,
    batch_analysis: BatchAnalysis,
    rating: Optional[int] = None,
    rating_type: Optional[str] = None,
) -> PlayerSnapshot:
    """
    Record a snapshot of player metrics after batch analysis.
    
    Called automatically after each batch analysis completes.
    """
    # Calculate metrics from batch
    avg_accuracy = 0.0
    avg_engine_agreement = 0.0
    
    if batch_analysis.games:
        accuracies = []
        agreements = []
        for game in batch_analysis.games:
            if game.investigation and game.investigation.details:
                details = game.investigation.details
                if "accuracy_estimate" in details:
                    accuracies.append(details["accuracy_estimate"])
                if "engine_agreement" in details:
                    agreements.append(details["engine_agreement"])
        
        if accuracies:
            avg_accuracy = sum(accuracies) / len(accuracies)
        if agreements:
            avg_engine_agreement = sum(agreements) / len(agreements)
    
    # Create snapshot
    snapshot = PlayerSnapshot(
        username=username.lower(),
        platform=platform,
        recorded_at=datetime.utcnow(),
        rating=rating,
        rating_type=rating_type,
        games_analyzed=batch_analysis.analyzed_count,
        avg_accuracy=avg_accuracy,
        avg_engine_agreement=avg_engine_agreement,
        avg_suspicion_score=batch_analysis.avg_suspicion,
        flagged_games_count=batch_analysis.flagged_count,
    )
    
    # Check for anomalies against historical data
    previous = get_previous_snapshot(db, username, platform)
    if previous:
        accuracy_jump = avg_accuracy - previous.avg_accuracy
        agreement_jump = avg_engine_agreement - previous.avg_engine_agreement
        
        # Flag suspicious jumps (>15% improvement in short time)
        if accuracy_jump > 0.15 or agreement_jump > 0.15:
            snapshot.anomaly_detected = True
            snapshot.anomaly_reason = f"Sudden improvement: accuracy +{accuracy_jump*100:.1f}%, agreement +{agreement_jump*100:.1f}%"
            snapshot.accuracy_trend = "suspicious_jump"
        elif accuracy_jump > 0.05:
            snapshot.accuracy_trend = "improving"
        elif accuracy_jump < -0.05:
            snapshot.accuracy_trend = "declining"
        else:
            snapshot.accuracy_trend = "stable"
    
    db.add(snapshot)
    db.flush()
    
    return snapshot


def get_previous_snapshot(
    db: Session,
    username: str,
    platform: str,
) -> Optional[PlayerSnapshot]:
    """Get the most recent snapshot for a player."""
    stmt = (
        select(PlayerSnapshot)
        .where(
            and_(
                PlayerSnapshot.username == username.lower(),
                PlayerSnapshot.platform == platform,
            )
        )
        .order_by(PlayerSnapshot.recorded_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_player_history(
    db: Session,
    username: str,
    platform: str,
    limit: int = 20,
) -> List[PlayerSnapshot]:
    """Get historical snapshots for a player."""
    stmt = (
        select(PlayerSnapshot)
        .where(
            and_(
                PlayerSnapshot.username == username.lower(),
                PlayerSnapshot.platform == platform,
            )
        )
        .order_by(PlayerSnapshot.recorded_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def analyze_trend(
    db: Session,
    username: str,
    platform: str,
) -> Optional[TrendAnalysis]:
    """
    Perform full trend analysis for a player.
    
    Returns None if no historical data is available.
    """
    snapshots = get_player_history(db, username, platform)
    
    if not snapshots:
        return None
    
    current = snapshots[0]
    
    # Build history for charting (reverse to chronological order)
    history = [
        {
            "date": s.recorded_at.isoformat(),
            "accuracy": round(s.avg_accuracy * 100, 1),
            "engine_agreement": round(s.avg_engine_agreement * 100, 1),
            "suspicion": round(s.avg_suspicion_score * 100, 1),
            "rating": s.rating,
            "games": s.games_analyzed,
        }
        for s in reversed(snapshots)
    ]
    
    # Calculate changes if we have history
    accuracy_change = 0.0
    agreement_change = 0.0
    rating_change = None
    
    if len(snapshots) > 1:
        oldest = snapshots[-1]
        accuracy_change = current.avg_accuracy - oldest.avg_accuracy
        agreement_change = current.avg_engine_agreement - oldest.avg_engine_agreement
        if current.rating and oldest.rating:
            rating_change = current.rating - oldest.rating
    
    # Determine overall trend
    if current.anomaly_detected:
        trend = "suspicious_jump"
        is_anomaly = True
        anomaly_reason = current.anomaly_reason
    elif accuracy_change > 0.10:
        trend = "improving"
        is_anomaly = accuracy_change > 0.20  # Very rapid improvement
        anomaly_reason = f"Rapid improvement of {accuracy_change*100:.1f}%" if is_anomaly else None
    elif accuracy_change < -0.05:
        trend = "declining"
        is_anomaly = False
        anomaly_reason = None
    else:
        trend = "stable"
        is_anomaly = False
        anomaly_reason = None
    
    return TrendAnalysis(
        username=username,
        platform=platform,
        snapshots_count=len(snapshots),
        current_accuracy=current.avg_accuracy,
        current_engine_agreement=current.avg_engine_agreement,
        current_rating=current.rating,
        accuracy_change=accuracy_change,
        agreement_change=agreement_change,
        rating_change=rating_change,
        trend=trend,
        is_anomaly=is_anomaly,
        anomaly_reason=anomaly_reason,
        history=history,
    )


def detect_anomalies_bulk(
    db: Session,
    days: int = 30,
) -> List[Tuple[str, str, str]]:
    """
    Scan all recent snapshots for anomalies.
    
    Returns list of (username, platform, reason) tuples.
    """
    since = datetime.utcnow() - timedelta(days=days)
    
    stmt = (
        select(PlayerSnapshot)
        .where(
            and_(
                PlayerSnapshot.anomaly_detected == True,
                PlayerSnapshot.recorded_at >= since,
            )
        )
        .order_by(PlayerSnapshot.recorded_at.desc())
    )
    
    results = db.execute(stmt).scalars().all()
    
    return [
        (s.username, s.platform, s.anomaly_reason or "Unknown")
        for s in results
    ]
