
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
import io

from server.database import get_db
from server.models.game import Game, InvestigationStatus
from server.services.reporting import generate_report

reporting_router = APIRouter(prefix="/api/reports", tags=["reporting"])

@reporting_router.get("/generate/{username}")
def download_evidence_report(
    username: str, 
    platform: str = "all",
    db: Session = Depends(get_db)
):
    """
    Generate and download a PDF Evidence Report for a player.
    Aggregates all flagged games and stats.
    """
    
    # 1. Fetch relevant games
    stmt = (
        select(Game)
        .join(Game.white_player)
        .join(Game.black_player)
        .where(
            (Game.white_player.has(username=username)) | 
            (Game.black_player.has(username=username))
        )
        .order_by(Game.played_at.desc())
    )
    
    all_games = db.execute(stmt).scalars().all()
    
    if not all_games:
        raise HTTPException(status_code=404, detail="No games found for this user")
        
    # 2. Extract Data for Report
    report_data = []
    for game in all_games:
        # Only include analyzed games
        if not game.investigation or not game.investigation.details:
            continue
            
        details = game.investigation.details
        suspicion = details.get("suspicion_score", 0.0)
        
        # Determine flags (reconstruct or read)
        flags = details.get("flags", [])
        
        game_info = {
            "white": game.white_player.username,
            "black": game.black_player.username,
            "result": game.result,
            "url": f"https://lichess.org/{game.lichess_id}" if game.source == "lichess" else f"https://chess.com/game/live/{game.lichess_id}",
            "suspicion_score": suspicion,
            "flags": flags,
            "sniper_gap": details.get("critical_vs_normal_gap", 0.0),
            "critical_accuracy": details.get("critical_moves_correct", 0) / details.get("critical_moves_total", 1) if details.get("critical_moves_total", 0) > 0 else 0,
            "engine_agreement": details.get("engine_agreement", 0.0)
        }
        report_data.append(game_info)
        
    if not report_data:
        raise HTTPException(status_code=400, detail="No analyzed games found with data. Run analysis first.")

    # 3. Generate PDF
    pdf_bytes = generate_report(username, platform, report_data)
    
    # 4. Return as File Download
    headers = {
        'Content-Disposition': f'attachment; filename="ChessGuard_Report_{username}.pdf"'
    }
    return Response(content=bytes(pdf_bytes), media_type="application/pdf", headers=headers)
