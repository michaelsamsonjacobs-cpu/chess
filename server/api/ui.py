from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from server.database import get_db
from server.database import get_db
from server.models.game import Game, InvestigationStatus, User, BatchAnalysis
from server.models.banned_player import BannedPlayer

from server.services.lichess import LichessService
from datetime import datetime

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ui_router = APIRouter(include_in_schema=False)


@ui_router.get("/")
def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@ui_router.get("/dashboard")
def dashboard_view(request: Request, db: Session = Depends(get_db)):
    """Main dashboard showing analyzed players and recent activity."""
    # Get distinct players from recent games
    recent_games = db.execute(
        select(Game)
        .options(
            selectinload(Game.white_player),
            selectinload(Game.black_player),
            selectinload(Game.investigation)
        )
        .order_by(Game.played_at.desc())
        .limit(100)
    ).scalars().all()
    
    # Build unique player list with game counts
    player_stats = {}
    for game in recent_games:
        for player in [game.white_player, game.black_player]:
            if player:
                if player.username not in player_stats:
                    player_stats[player.username] = {
                        'username': player.username,
                        'game_count': 0,
                        'flagged_count': 0,
                        'pending_count': 0,
                        'platform': getattr(game, 'source', 'All')
                    }
                player_stats[player.username]['game_count'] += 1
                if game.investigation and game.investigation.details:
                    score = game.investigation.details.get('suspicion_score', 0)
                    if score > 0.8:
                        player_stats[player.username]['flagged_count'] += 1
                if game.analysis_status == InvestigationStatus.PENDING:
                    player_stats[player.username]['pending_count'] += 1
    
    # Sort by game count, limit to top 20
    players = sorted(player_stats.values(), key=lambda x: x['game_count'], reverse=True)[:20]
    
    # Stats
    total_games = len(recent_games)
    total_flagged = sum(1 for g in recent_games if g.analysis_status == InvestigationStatus.FLAGGED)
    total_pending = sum(1 for g in recent_games if g.analysis_status == InvestigationStatus.PENDING)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "players": players,
            "stats": {
                "total_games": total_games,
                "flagged": total_flagged,
                "pending": total_pending,
                "players_tracked": len(players)
            }
        }
    )


@ui_router.get("/analyses")
def analyses_view(
    request: Request,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = select(Game).options(
        selectinload(Game.white_player),
        selectinload(Game.black_player),
        selectinload(Game.evaluations)
    ).order_by(Game.played_at.desc())

    if status:
        query = query.where(Game.analysis_status == InvestigationStatus(status))

    if search:
        search_term = f"%{search}%"
        query = query.join(User, or_(Game.white_id == User.id, Game.black_id == User.id))\
                     .where(or_(User.username.ilike(search_term), Game.result.ilike(search_term)))

    games = db.execute(query).scalars().all()

    return templates.TemplateResponse(
        "analyses.html",
        {
            "request": request,
            "games": games,
            "status_options": [s.value for s in InvestigationStatus],
            "status_filter": status,
            "search_filter": search
        }
    )


@ui_router.get("/analyses/{game_id}")
def analysis_detail_view(request: Request, game_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(Game)
        .where(Game.id == game_id)
        .options(
            selectinload(Game.white_player),
            selectinload(Game.black_player),
            selectinload(Game.investigation),
            selectinload(Game.evaluations),
        )
    )
    game = db.execute(stmt).scalars().first()
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return templates.TemplateResponse(
        "analysis_detail.html",
        {
            "request": request,
            "game": game,
            "status_options": list(InvestigationStatus),
        },
    )


@ui_router.get("/player/{username}")
def player_profile_view(
    request: Request,
    username: str,
    opponent: Optional[str] = Query(None, description="Filter by opponent username"),
    result_status: Optional[str] = Query(None, alias="status", description="Filter by analysis status"),
    db: Session = Depends(get_db)
):
    # 1. Fetch User ID first (safer than complex joins)
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"Player {username} not found")
        
    # 2. Find games by ID
    stmt = (
        select(Game)
        .where(
            or_(
                Game.white_id == user.id,
                Game.black_id == user.id
            )
        )
        .options(
            selectinload(Game.white_player),
            selectinload(Game.black_player),
            selectinload(Game.investigation),
        )
        .order_by(Game.played_at.desc().nullslast())
    )
    
    # Apply status filter
    if result_status:
        try:
            status_enum = InvestigationStatus(result_status)
            stmt = stmt.where(Game.analysis_status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter
    
    games = db.execute(stmt).scalars().all()
    
    # Apply opponent filter in Python (easier than complex join)
    if opponent:
        opponent_lower = opponent.lower()
        games = [
            g for g in games
            if (g.white_player and g.white_player.username.lower() == opponent_lower and g.black_player and g.black_player.username.lower() == username.lower())
            or (g.black_player and g.black_player.username.lower() == opponent_lower and g.white_player and g.white_player.username.lower() == username.lower())
        ]
    
    # Get list of unique opponents for the filter dropdown
    all_opponents = set()
    for g in db.execute(
        select(Game)
        .where(or_(Game.white_id == user.id, Game.black_id == user.id))
        .options(selectinload(Game.white_player), selectinload(Game.black_player))
    ).scalars().all():
        if g.white_player and g.white_player.username.lower() != username.lower():
            all_opponents.add(g.white_player.username)
        if g.black_player and g.black_player.username.lower() != username.lower():
            all_opponents.add(g.black_player.username)
    
    return templates.TemplateResponse(
        "player_profile.html",
        {
            "request": request,
            "username": username,
            "games": games,
            "opponents": sorted(all_opponents),
            "status_options": [s.value for s in InvestigationStatus],
            "current_opponent": opponent,
            "current_status": result_status,
        },
    )


@ui_router.get("/cheaters")
def cheaters_list_view(request: Request, db: Session = Depends(get_db)):
    # Fetch recent bans
    bans = db.execute(select(BannedPlayer).order_by(BannedPlayer.first_seen.desc()).limit(100)).scalars().all()
    stats = {
        "total": db.query(BannedPlayer).count(),
        "lichess": db.query(BannedPlayer).filter(BannedPlayer.platform=="lichess").count(),
        "chesscom": db.query(BannedPlayer).filter(BannedPlayer.platform=="chesscom").count()
    }
    return templates.TemplateResponse(
        "cheaters.html",
        {"request": request, "bans": bans, "stats": stats}
    )


@ui_router.get("/batch")
def batch_dashboard_view(request: Request, db: Session = Depends(get_db)):
    # Fetch recent batch jobs
    jobs = db.execute(select(BatchAnalysis).order_by(BatchAnalysis.started_at.desc()).limit(20)).scalars().all()
    return templates.TemplateResponse(
        "batch.html",
        {"request": request, "jobs": jobs}
    )


@ui_router.get("/detective")
def detective_view(request: Request, db: Session = Depends(get_db)):
    # Fetch distinct recent players (simple heuristic: recent games)
    # Using a simple list for now, optimization can come later
    stmt = select(Game).order_by(Game.played_at.desc()).limit(10)
    games = db.execute(stmt).scalars().all()
    recent = list(set([g.white_player.username for g in games] + [g.black_player.username for g in games]))[:6]
    
    return templates.TemplateResponse(
        "detective.html",
        {"request": request, "recent_searches": recent}
    )


@ui_router.get("/connect")
def connect_view(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get("chessguard_user")
    user = None
    if username:
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    
    return templates.TemplateResponse(
        "connect.html",
        {"request": request, "user": user}
    )


@ui_router.post("/connect")
async def connect_submit(
    request: Request,
    username: str = Form(...),
    token: str = Form(None),
    db: Session = Depends(get_db)
):
    # Upsert user
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user:
        user = User(username=username, lichess_username=username)
        db.add(user)
    
    if token:
        user.lichess_token = token
        user.lichess_username = username # Ensure linked
    
    db.commit()
    
    response = RedirectResponse(url="/connect", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="chessguard_user", value=username)
    return response


@ui_router.post("/api/sync")
async def sync_games(
    username: str, # passed as query param
    limit: int = 10,
    db: Session = Depends(get_db)
):
    # Get user token
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user or not user.lichess_token:
        return JSONResponse(status_code=400, content={"detail": "User not connected or no token"})

    service = LichessService()
    try:
        games_data = await service.fetch_recent_games(
            username=username,
            token=user.lichess_token,
            max_games=limit
        )
        
        imported = 0
        for g in games_data:
            # Check existence
            lid = g.get("id")
            exists = db.execute(select(Game).where(Game.lichess_id == lid)).scalar_one_or_none()
            if exists:
                continue
            
            # Create players if needed
            w_name = g.get("white")
            b_name = g.get("black")
            
            white = db.execute(select(User).where(User.username == w_name)).scalar_one_or_none()
            if not white:
                white = User(username=w_name, lichess_username=w_name)
                db.add(white)
                db.flush() # get ID
            
            black = db.execute(select(User).where(User.username == b_name)).scalar_one_or_none()
            if not black:
                black = User(username=b_name, lichess_username=b_name)
                db.add(black)
                db.flush()
            
            # Parse time
            played_at = None
            if g.get("createdAt"):
                try:
                    played_at = datetime.fromtimestamp(g.get("createdAt") / 1000)
                except: pass

            game = Game(
                lichess_id=lid,
                white_id=white.id,
                black_id=black.id,
                result=g.get("winner"), # 'white', 'black', or None (draw)
                pgn=g.get("pgn"),
                played_at=played_at,
                source="lichess",
                analysis_status=InvestigationStatus.PENDING
            )
            db.add(game)
            imported += 1
        
        db.commit()
        return {"imported": imported}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        await service.aclose()
