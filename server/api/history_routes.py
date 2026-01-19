"""
History and Player Tracking API Routes

Endpoints for accessing player historical data and trend analysis.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db
from server.services import history_service


history_router = APIRouter(prefix="/api/history", tags=["history"])


class SnapshotResponse(BaseModel):
    """Response for a single snapshot."""
    id: int
    username: str
    platform: str
    recorded_at: str
    rating: Optional[int]
    games_analyzed: int
    avg_accuracy: float
    avg_engine_agreement: float
    avg_suspicion_score: float
    flagged_games_count: int
    accuracy_trend: Optional[str]
    anomaly_detected: bool
    anomaly_reason: Optional[str]

    class Config:
        from_attributes = True


class TrendResponse(BaseModel):
    """Response for trend analysis."""
    username: str
    platform: str
    snapshots_count: int
    current_accuracy: float
    current_engine_agreement: float
    current_rating: Optional[int]
    accuracy_change: float
    agreement_change: float
    rating_change: Optional[int]
    trend: str
    is_anomaly: bool
    anomaly_reason: Optional[str]
    history: List[dict]


class AnomalyResponse(BaseModel):
    """Response for anomaly detection."""
    username: str
    platform: str
    reason: str


@history_router.get("/{platform}/{username}", response_model=List[SnapshotResponse])
def get_player_history(
    platform: str,
    username: str,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Get historical snapshots for a player."""
    snapshots = history_service.get_player_history(
        db=db,
        username=username,
        platform=platform,
        limit=limit,
    )
    
    return [
        SnapshotResponse(
            id=s.id,
            username=s.username,
            platform=s.platform,
            recorded_at=s.recorded_at.isoformat(),
            rating=s.rating,
            games_analyzed=s.games_analyzed,
            avg_accuracy=s.avg_accuracy,
            avg_engine_agreement=s.avg_engine_agreement,
            avg_suspicion_score=s.avg_suspicion_score,
            flagged_games_count=s.flagged_games_count,
            accuracy_trend=s.accuracy_trend,
            anomaly_detected=s.anomaly_detected,
            anomaly_reason=s.anomaly_reason,
        )
        for s in snapshots
    ]


@history_router.get("/{platform}/{username}/trend", response_model=TrendResponse)
def get_player_trend(
    platform: str,
    username: str,
    db: Session = Depends(get_db),
):
    """Get trend analysis for a player."""
    trend = history_service.analyze_trend(
        db=db,
        username=username,
        platform=platform,
    )
    
    if not trend:
        raise HTTPException(status_code=404, detail="No historical data for this player")
    
    return TrendResponse(
        username=trend.username,
        platform=trend.platform,
        snapshots_count=trend.snapshots_count,
        current_accuracy=trend.current_accuracy,
        current_engine_agreement=trend.current_engine_agreement,
        current_rating=trend.current_rating,
        accuracy_change=trend.accuracy_change,
        agreement_change=trend.agreement_change,
        rating_change=trend.rating_change,
        trend=trend.trend,
        is_anomaly=trend.is_anomaly,
        anomaly_reason=trend.anomaly_reason,
        history=trend.history,
    )


@history_router.get("/anomalies", response_model=List[AnomalyResponse])
def get_recent_anomalies(
    days: int = Query(30, le=365),
    db: Session = Depends(get_db),
):
    """Get all players with recent anomalies."""
    anomalies = history_service.detect_anomalies_bulk(db=db, days=days)
    
    return [
        AnomalyResponse(username=u, platform=p, reason=r)
        for u, p, r in anomalies
    ]
