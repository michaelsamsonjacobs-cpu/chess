"""Lichess audit API endpoints for Detective Mode."""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Dict, Any

import httpx

router = APIRouter(prefix="/api/audit/lichess", tags=["lichess-audit"])

LICHESS_API_BASE = "https://lichess.org/api"


async def fetch_lichess_public_games(username: str, max_games: int = 50) -> List[Dict[str, Any]]:
    """Fetch public games for any Lichess user (no auth required)."""
    url = f"{LICHESS_API_BASE}/games/user/{username}"
    headers = {
        "Accept": "application/x-ndjson",
        "User-Agent": "ChessGuard/1.0"
    }
    params = {
        "max": max_games,
        "pgnInJson": "true",
        "clocks": "true",
        "opening": "true",
    }
    
    games = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream("GET", url, headers=headers, params=params) as response:
            if response.status_code == 404:
                return []
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.strip():
                    import json
                    game = json.loads(line)
                    games.append(game)
    
    return games


@router.get("/{username}/games")
async def get_lichess_games(
    username: str, 
    max_games: int = Query(50, le=100, ge=1)
) -> List[Dict[str, Any]]:
    """
    Fetch public games for a Lichess user (Auditor/Detective Mode).
    No authentication required - uses public API.
    """
    try:
        games = await fetch_lichess_public_games(username, max_games)
        if not games:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lichess user '{username}' not found or has no public games."
            )
        
        # Transform to consistent format
        result = []
        for g in games:
            players = g.get("players", {})
            white = players.get("white", {})
            black = players.get("black", {})
            
            result.append({
                "id": g.get("id"),
                "url": f"https://lichess.org/{g.get('id')}",
                "pgn": g.get("pgn", ""),
                "white": {
                    "username": white.get("user", {}).get("name", "Anonymous"),
                    "rating": white.get("rating", 0),
                    "result": "win" if g.get("winner") == "white" else ("loss" if g.get("winner") == "black" else "draw")
                },
                "black": {
                    "username": black.get("user", {}).get("name", "Anonymous"),
                    "rating": black.get("rating", 0),
                    "result": "win" if g.get("winner") == "black" else ("loss" if g.get("winner") == "white" else "draw")
                },
                "speed": g.get("speed", "unknown"),
                "status": g.get("status", "unknown"),
                "createdAt": g.get("createdAt"),
            })
        
        return result
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching from Lichess: {e}"
        )


@router.get("/{username}/status")
async def get_lichess_player_status(username: str) -> Dict[str, Any]:
    """
    Check if a Lichess player account is marked for TOS violation (cheating).
    
    Returns player profile with:
    - tosViolation: true if account is marked as cheater
    - disabled: true if account is closed/banned
    - Additional profile info
    """
    url = f"{LICHESS_API_BASE}/user/{username}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "ChessGuard/1.0"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers)
        
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lichess user '{username}' not found."
            )
        
        response.raise_for_status()
        user_data = response.json()
        
        # Check for TOS violation (cheater mark)
        tos_violation = user_data.get("tosViolation", False)
        disabled = user_data.get("disabled", False)
        
        return {
            "username": user_data.get("username"),
            "platform": "lichess",
            "tos_violation": tos_violation,
            "is_cheater_marked": tos_violation,
            "account_disabled": disabled,
            "account_closed": user_data.get("closed", False),
            "title": user_data.get("title"),
            "created_at": user_data.get("createdAt"),
            "seen_at": user_data.get("seenAt"),
            "play_time_total": user_data.get("playTime", {}).get("total", 0),
            "count": user_data.get("count", {}),
            "profile_url": f"https://lichess.org/@/{username}",
            "training_value": "HIGH" if tos_violation else "LOW",  # Confirmed cheaters are valuable for training
        }

