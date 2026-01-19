
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
GAMES_DIR = DATA_DIR / "gm_games"
GAMES_DIR.mkdir(parents=True, exist_ok=True)

# Top GMs on Chess.com / Lichess
TARGETS = [
    {"username": "MagnusCarlsen", "platform": "chesscom", "name": "Magnus Carlsen"},
    {"username": "Hikaru", "platform": "chesscom", "name": "Hikaru Nakamura"},
    {"username": "FabianoCaruana", "platform": "chesscom", "name": "Fabiano Caruana"},
    {"username": "Firouzja2003", "platform": "chesscom", "name": "Alireza Firouzja"},
    {"username": "DrNykterstein", "platform": "lichess", "name": "Magnus Carlsen (Lichess)"},
    {"username": "rebeig", "platform": "lichess", "name": "Rebecca (Daniel Naroditsky)"},
    {"username": "Penguingim1", "platform": "lichess", "name": "Andrew Tang"},
    {"username": "BigChunk", "platform": "chesscom", "name": "Praggnanandhaa R"},
    {"username": "GMWSO", "platform": "chesscom", "name": "Wesley So"},
    {"username": "lachesisQ", "platform": "chesscom", "name": "Ian Nepomniachtchi"}
]

HEADERS = {
    "User-Agent": "ChessGuard/1.0 (research@chessguard.dev)"
}

async def fetch_games():
    print(f"Fetching games for {len(TARGETS)} top GMs...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for target in TARGETS:
            username = target["username"]
            platform = target["platform"]
            print(f"\n👑 Processing {target['name']} ({username} on {platform})...")
            
            games = []
            
            try:
                if platform == "chesscom":
                    # Fetch archives
                    url = f"https://api.chess.com/pub/player/{username}/games/archives"
                    resp = await client.get(url, headers=HEADERS)
                    if resp.status_code == 200:
                        archives = resp.json().get("archives", [])
                        if archives:
                            # Get last archive
                            last_archive = archives[-1]
                            print(f"  Fetching archive: {last_archive}...")
                            resp = await client.get(last_archive, headers=HEADERS)
                            if resp.status_code == 200:
                                games = resp.json().get("games", [])
                                # Reverse to get newest first
                                games.reverse()
                                
                elif platform == "lichess":
                    # Fetch recent games
                    url = f"https://lichess.org/api/games/user/{username}"
                    params = {"max": 50, "pgnInJson": "true", "perfType": "blitz"}
                    headers = {**HEADERS, "Accept": "application/x-ndjson"}
                    
                    async with client.stream("GET", url, headers=headers, params=params) as resp:
                        async for line in resp.aiter_lines():
                            if line.strip():
                                games.append(json.loads(line))
                                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
            
            # Save games
            if games:
                # Limit to 50 games max per player for this validation set
                games = games[:50]
                
                filename = GAMES_DIR / f"{platform}_{username}.json"
                with open(filename, "w") as f:
                    json.dump(games, f)
                print(f"  ✅ Saved {len(games)} games to {filename.name}")
            else:
                print("  ⚠️ No games found.")
                
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(fetch_games())
