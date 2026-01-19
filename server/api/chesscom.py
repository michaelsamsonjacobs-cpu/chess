
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any

from ..services.chesscom import chesscom_service

router = APIRouter(prefix="/api/audit/chesscom", tags=["chesscom"])

@router.get("/{username}/games")
async def get_chesscom_games(username: str, limit_months: int = 1) -> List[Dict[str, Any]]:
    """
    Fetch public games for a Chess.com user (Auditor/Detective Mode).
    """
    profile = await chesscom_service.get_player_profile(username)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chess.com user '{username}' not found."
        )

    games = await chesscom_service.get_recent_games(username, limit_months=limit_months)
    return games


@router.get("/{username}/status")
async def get_chesscom_player_status(username: str) -> Dict[str, Any]:
    """
    Check Chess.com player account status.
    """
    try:
        user_data = await chesscom_service.get_player_profile(username)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chess.com user '{username}' not found."
            )
        
        # Chess.com uses 'status' field: 'basic', 'premium', 'closed:fair_play_violations', etc.
        account_status = user_data.get("status", "unknown")
        is_closed_fair_play = "closed:fair_play" in account_status.lower() if account_status else False
        is_closed = account_status.startswith("closed") if account_status else False
        
        return {
            "username": user_data.get("username"),
            "platform": "chesscom",
            "status": account_status,
            "is_cheater_marked": is_closed_fair_play,
            "account_closed": is_closed,
            "title": user_data.get("title"),
            "joined": user_data.get("joined"),
            "last_online": user_data.get("last_online"),
            "profile_url": user_data.get("url", f"https://chess.com/member/{username}"),
            "training_value": "HIGH" if is_closed_fair_play else "LOW",
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking Chess.com status: {str(e)}"
        )
