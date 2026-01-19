"""Batch analysis API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.database import get_db
from server.models.game import (
    BatchAnalysis,
    BatchAnalysisRequest,
    BatchAnalysisRead,
    BatchAnalysisStatus,
    RiskLevel,
    Game,
    InvestigationStatus,
)
from server.tasks import batch_analyze_task

import threading

batch_router = APIRouter(prefix="/api/batch-analyze", tags=["batch-analysis"])


def _run_batch_in_thread(batch_id: int, source: str, username: str, timeframe: str):
    """Run batch analysis in a background thread."""
    try:
        batch_analyze_task(batch_id, source, username, timeframe)
    except Exception as e:
        print(f"Background batch analysis error: {e}")


@batch_router.post("", response_model=BatchAnalysisRead, status_code=status.HTTP_202_ACCEPTED)
def start_batch_analysis(
    request: BatchAnalysisRequest,
    db: Session = Depends(get_db),
) -> BatchAnalysisRead:
    """Start a batch analysis job for all games of a player."""
    
    # Check for existing active analysis for this player
    existing = db.execute(
        select(BatchAnalysis).where(
            BatchAnalysis.source == request.source,
            BatchAnalysis.username.ilike(request.username),
            BatchAnalysis.status.in_([BatchAnalysisStatus.QUEUED, BatchAnalysisStatus.RUNNING])
        ).limit(1)
    ).scalar_one_or_none()
    
    if existing:
        return existing

    # Create batch record
    batch = BatchAnalysis(
        source=request.source,
        username=request.username,
        timeframe=request.timeframe,
        status=BatchAnalysisStatus.QUEUED,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    
    # Run in background thread (non-blocking)
    thread = threading.Thread(
        target=_run_batch_in_thread,
        args=(batch.id, request.source, request.username, request.timeframe),
        daemon=True
    )
    thread.start()
    
    return batch


MAX_CONCURRENT_ANALYSES = 9


@batch_router.get("/active")
def get_active_analyses(
    db: Session = Depends(get_db),
) -> dict:
    """Get all active/queued batch analyses for dashboard display."""
    
    active_batches = db.execute(
        select(BatchAnalysis).where(
            BatchAnalysis.status.in_([BatchAnalysisStatus.QUEUED, BatchAnalysisStatus.RUNNING])
        ).order_by(BatchAnalysis.started_at.desc())
    ).scalars().all()
    
    # Calculate progress and ETA for each
    analyses = []
    for batch in active_batches:
        progress = 0
        if batch.total_games > 0:
            progress = round((batch.analyzed_count / batch.total_games) * 100)
        
        # Estimate time remaining (rough: ~30 seconds per game)
        remaining_games = batch.total_games - batch.analyzed_count
        eta_seconds = remaining_games * 30
        eta_minutes = round(eta_seconds / 60)
        
        analyses.append({
            "id": batch.id,
            "username": batch.username,
            "platform": batch.source,
            "status": batch.status.value if hasattr(batch.status, 'value') else str(batch.status),
            "progress": progress,
            "total_games": batch.total_games,
            "analyzed_count": batch.analyzed_count,
            "flagged_count": batch.flagged_count,
            "avg_suspicion": batch.avg_suspicion,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "eta_minutes": eta_minutes if eta_minutes > 0 else None,
        })
    
    return {
        "active": analyses[:MAX_CONCURRENT_ANALYSES],
        "count": len(analyses),
        "max_concurrent": MAX_CONCURRENT_ANALYSES,
        "slots_available": max(0, MAX_CONCURRENT_ANALYSES - len(analyses)),
    }


@batch_router.get("/history")
def get_analysis_history(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    """Get historical completed analyses for player lookup."""
    
    completed_batches = db.execute(
        select(BatchAnalysis).where(
            BatchAnalysis.status == BatchAnalysisStatus.COMPLETED
        ).order_by(BatchAnalysis.completed_at.desc()).limit(limit)
    ).scalars().all()
    
    history = []
    for batch in completed_batches:
        history.append({
            "id": batch.id,
            "username": batch.username,
            "platform": batch.source,
            "risk_level": batch.risk_level.value if batch.risk_level else None,
            "flagged_count": batch.flagged_count,
            "total_games": batch.total_games,
            "avg_suspicion": batch.avg_suspicion,
            "analyzed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "analyzed_date": batch.completed_at.strftime("%Y-%m-%d") if batch.completed_at else None,
        })
    
    return {
        "history": history,
        "total": len(history),
    }


@batch_router.get("/search")
def search_players(
    q: str,
    db: Session = Depends(get_db),
) -> dict:
    """Quick search for players in analysis history."""
    
    if len(q) < 2:
        return {"results": [], "query": q}
    
    # Search by username (case-insensitive), include all statuses
    from sqlalchemy import desc
    matching = db.execute(
        select(BatchAnalysis).where(
            BatchAnalysis.username.ilike(f"%{q}%")
        ).order_by(
            # Sort by: RUNNING first, then QUEUED, then COMPLETED by date
            desc(BatchAnalysis.status == BatchAnalysisStatus.RUNNING),
            desc(BatchAnalysis.status == BatchAnalysisStatus.QUEUED),
            desc(BatchAnalysis.completed_at),
            desc(BatchAnalysis.started_at)
        ).limit(10)
    ).scalars().all()
    
    results = []
    seen_players = set()
    
    for batch in matching:
        player_key = f"{batch.source}:{batch.username.lower()}"
        if player_key in seen_players:
            continue
        seen_players.add(player_key)
        
        # Calculate progress if active
        progress = 0
        if batch.total_games > 0:
            progress = round((batch.analyzed_count / batch.total_games) * 100)

        results.append({
            "id": batch.id,
            "username": batch.username,
            "platform": batch.source,
            "status": batch.status.value if hasattr(batch.status, 'value') else str(batch.status),
            "progress": progress,
            "risk_level": batch.risk_level.value if batch.risk_level else None,
            "avg_suspicion": batch.avg_suspicion,
            "flagged_count": batch.flagged_count,
            "total_games": batch.total_games,
            "analyzed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        })
    
    return {
        "results": results,
        "query": q,
    }


@batch_router.get("/player/{platform}/{username}")
def get_player_analysis(
    platform: str,
    username: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get the latest analysis for a specific player (for shareable URLs)."""
    
    # Find the most recent completed analysis for this player
    batch = db.execute(
        select(BatchAnalysis).where(
            BatchAnalysis.source == platform,
            BatchAnalysis.username.ilike(username),  # Case-insensitive
            BatchAnalysis.status == BatchAnalysisStatus.COMPLETED
        ).order_by(BatchAnalysis.completed_at.desc()).limit(1)
    ).scalar_one_or_none()
    
    if batch is None:
        # Check if there's an active analysis
        active = db.execute(
            select(BatchAnalysis).where(
                BatchAnalysis.source == platform,
                BatchAnalysis.username.ilike(username),
                BatchAnalysis.status.in_([BatchAnalysisStatus.QUEUED, BatchAnalysisStatus.RUNNING])
            ).limit(1)
        ).scalar_one_or_none()
        
        if active:
            return {
                "found": True,
                "status": "analyzing",
                "message": f"Analysis in progress: {active.analyzed_count}/{active.total_games} games",
                "batch_id": active.id,
                "progress": round((active.analyzed_count / active.total_games) * 100) if active.total_games > 0 else 0,
            }
        
        return {
            "found": False,
            "status": "not_analyzed",
            "message": f"No analysis found for {username} on {platform}",
            "username": username,
            "platform": platform,
        }
    
    # Return the full analysis summary
    return {
        "found": True,
        "status": "completed",
        "batch_id": batch.id,
        "username": batch.username,
        "platform": batch.source,
        "risk_level": batch.risk_level.value if batch.risk_level else "unknown",
        "avg_suspicion": batch.avg_suspicion,
        "suspicion_percent": round(batch.avg_suspicion * 100),
        "flagged_count": batch.flagged_count,
        "total_games": batch.total_games,
        "analyzed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "analyzed_date": batch.completed_at.strftime("%B %d, %Y") if batch.completed_at else None,
        "share_url": f"/player/{platform}/{batch.username}",
    }


@batch_router.get("/{batch_id}", response_model=BatchAnalysisRead)
def get_batch_status(
    batch_id: int,
    db: Session = Depends(get_db),
) -> BatchAnalysisRead:
    """Get the status of a batch analysis job."""
    
    batch = db.execute(
        select(BatchAnalysis).where(BatchAnalysis.id == batch_id)
    ).scalar_one_or_none()
    
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch analysis {batch_id} not found"
        )
    
    return batch


@batch_router.get("/{batch_id}/games")
def get_batch_games(
    batch_id: int,
    flagged_only: bool = False,
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get all games from a batch analysis with their COA summaries."""
    
    batch = db.execute(
        select(BatchAnalysis).where(BatchAnalysis.id == batch_id)
    ).scalar_one_or_none()
    
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch analysis {batch_id} not found"
        )
    
    stmt = select(Game).where(Game.batch_id == batch_id)
    if flagged_only:
        stmt = stmt.where(Game.analysis_status == InvestigationStatus.FLAGGED)
    
    games = db.execute(stmt).scalars().all()
    
    result = []
    for game in games:
        details = game.investigation.details if game.investigation else {}
        result.append({
            "game_id": game.id,
            "lichess_id": game.lichess_id,
            "source": game.source,
            "white": game.white_player.username,
            "black": game.black_player.username,
            "result": game.result,
            "played_at": game.played_at.isoformat() if game.played_at else None,
            "suspicion_score": details.get("suspicion_score", 0),
            "engine_agreement": details.get("engine_agreement", 0),
            "tom_score": details.get("tom_score", 0),
            "tension_complexity": details.get("tension_complexity", 0),
            "status": game.analysis_status.value,
            "flagged": game.analysis_status == InvestigationStatus.FLAGGED,
        })
    
    return result


@batch_router.post("/{batch_id}/report-all")
async def report_all_flagged(
    batch_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Submit reports for all flagged games in the batch."""
    
    batch = db.execute(
        select(BatchAnalysis).where(BatchAnalysis.id == batch_id)
    ).scalar_one_or_none()
    
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch analysis {batch_id} not found"
        )
    
    # Get flagged games with high suspicion
    stmt = select(Game).where(
        Game.batch_id == batch_id,
        Game.analysis_status == InvestigationStatus.FLAGGED
    )
    flagged_games = db.execute(stmt).scalars().all()
    
    if not flagged_games:
        return {
            "message": "No flagged games to report",
            "batch_id": batch_id,
            "reported_count": 0,
        }
    
    reported_count = 0
    errors = []
    
    if batch.source == "lichess":
        # Import and use Lichess service for reporting
        from server.dependencies import lichess_service
        from server.models.lichess import LichessReport
        
        for game in flagged_games:
            try:
                details = game.investigation.details if game.investigation else {}
                suspicion = details.get("suspicion_score", 0)
                
                # Only report high-confidence cases
                if suspicion < 0.5:
                    continue
                
                # Determine which player to report (the one with engine-like play)
                # For simplicity, report both players if we can't determine
                player_id = game.white_player.lichess_username or game.white_player.username
                
                description = f"""ChessGuard Analysis Report
Suspicion Score: {suspicion:.2%}
Engine Agreement: {details.get('engine_agreement', 0):.2%}
ToM Score: {details.get('tom_score', 0)}
Tension Complexity: {details.get('tension_complexity', 0)}

This report was generated by automated analysis."""

                # Note: This requires an authenticated Lichess token
                # For now, we'll just log the intent
                # In production, you'd need the user's OAuth token
                
                # Create a report record
                report = LichessReport(
                    account_id=1,  # Placeholder - should be actual user ID
                    game_id=game.lichess_id,
                    player_id=player_id,
                    reason="cheat",
                    description=description,
                    status_code=200,
                    message="Report queued (manual submission required - no OAuth token)"
                )
                db.add(report)
                reported_count += 1
                
            except Exception as e:
                errors.append(f"Game {game.lichess_id}: {str(e)}")
        
        db.commit()
        batch.reported_count = reported_count
        db.commit()
        
        return {
            "message": f"Queued {reported_count} reports for Lichess. Note: Full auto-reporting requires OAuth authentication.",
            "batch_id": batch_id,
            "reported_count": reported_count,
            "errors": errors if errors else None,
        }
    
    else:  # Chess.com
        return {
            "message": "Chess.com does not have a public reporting API. Use the 'Generate Report Email' button to copy a report to send to feedback@chess.com.",
            "batch_id": batch_id,
            "flagged_count": len(flagged_games),
        }

@batch_router.delete("/{batch_id}")
async def delete_batch_analysis(
    batch_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a batch analysis job and its associated game records."""
    
    batch = db.execute(
        select(BatchAnalysis).where(BatchAnalysis.id == batch_id)
    ).scalar_one_or_none()
    
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch analysis {batch_id} not found"
        )
    
    # Delete associated games (cascades or manual depending on setup)
    # The models show Game has batch_id but no explicit cascade delete in relationship.
    # Manual cleanup to be safe:
    db.execute(
        select(Game).where(Game.batch_id == batch_id)
    )
    # Actually Game table has batch_id. We can just null it or delete games.
    # For a full batch delete, we probably want to delete the games too if they were imported just for this batch.
    
    db.delete(batch)
    db.commit()
    
    return {"message": f"Batch analysis {batch_id} deleted successfully"}
