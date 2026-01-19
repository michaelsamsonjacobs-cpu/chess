"""
Discover banned/closed accounts to build a training dataset.
Strategies:
1. Scan opponents of popular/active players (BFS Crawler)
2. Check account status for 'closed:fair_play_violations' (Chess.com)
3. Save confirmed cheaters to database
"""

import asyncio
import json
import httpx
import time
import random
from pathlib import Path
from typing import List, Dict, Set

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
CHEATERS_FILE = DATA_DIR / "known_cheaters.json"

class CheaterDiscoverer:
    def __init__(self):
        self.headers = {"User-Agent": "ChessGuard/1.0 (research@chessguard.dev)"}
        self.cheaters: List[Dict] = []
        self.scanned_count = 0
        
        # Load existing
        if CHEATERS_FILE.exists():
            with open(CHEATERS_FILE, "r") as f:
                data = json.load(f)
                self.cheaters = data.get("titled_cheaters", [])
                
        self.existing_usernames = {c["username"].lower() for c in self.cheaters}
        print(f"Loaded {len(self.cheaters)} existing known cheaters.")

    async def fetch_recent_opponents(self, username: str, limit=50) -> List[str]:
        """Fetch recent opponents of a player."""
        opponents = set()
        url = f"https://api.chess.com/pub/player/{username.lower()}/games/archives"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                # Get archives
                resp = await client.get(url, headers=self.headers)
                if resp.status_code != 200:
                    return []
                archives = resp.json().get("archives", [])
                
                # Check last 1-2 months
                for archive_url in reversed(archives[-2:]):
                    resp = await client.get(archive_url, headers=self.headers)
                    if resp.status_code == 200:
                        games = resp.json().get("games", [])
                        for game in reversed(games):
                            if len(opponents) >= limit:
                                break
                                
                            # Extract opponent
                            white = game.get("white", {}).get("username")
                            black = game.get("black", {}).get("username")
                            
                            if white and white.lower() != username.lower():
                                opponents.add(white)
                            if black and black.lower() != username.lower():
                                opponents.add(black)
                        
                        if len(opponents) >= limit:
                            break
            except Exception as e:
                pass
        return list(opponents)

    async def scan_via_crawler(self, target_new_cheaters=100):
        """BFS Crawler to find cheaters by scanning opponents."""
        print(f"Starting BFS Crawler to find {target_new_cheaters} new untitled/titled cheaters...")
        
        # Seed players (Active heavy users) - Lowercase to avoid redirects
        seeds = [
            "hikaru", "gothamchess", "danielnaroditsky", "magnuscarlsen", 
            "botez", "annacramling", "hansniemann", "kramnik",
            "ericrosen", "nemo", "akanemsko"
        ]
        
        queue = list(seeds)
        visited = set(self.existing_usernames)
        visited.update(s.lower() for s in seeds)
        
        initial_count = len(self.cheaters)
        sem = asyncio.Semaphore(25)  # Concurrency limit
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            while len(queue) > 0:
                # Check stop condition
                current_new = len(self.cheaters) - initial_count
                if current_new >= target_new_cheaters:
                    print(f"\nTarget reached! Found {current_new} new cheaters.")
                    break
                
                # Pop a "hub" player
                hub_user = queue.pop(0)

                # Fetch opponents
                opponents = await self.fetch_recent_opponents(hub_user, limit=50)
                
                # Filter previously visited
                to_check = []
                for opp in opponents:
                    if opp.lower() not in visited:
                        to_check.append(opp)
                        visited.add(opp.lower())
                
                print(f"  Checking {len(to_check)} opponents of {hub_user}...")
                
                if not to_check:
                    continue

                # Check status of these opponents concurrently
                tasks = []
                for username in to_check:
                    task = self.check_chesscom_player_controlled(username, client, sem)
                    tasks.append(task)
                
                # Results calculation
                for future in asyncio.as_completed(tasks):
                    await future
                    self.scanned_count += 1
                    
                    current_new = len(self.cheaters) - initial_count
                    if self.scanned_count % 50 == 0:
                         print(f"  Progress: Checked {self.scanned_count} players. Found {current_new}/{target_new_cheaters} new cheaters.")
                         
                    # INCREMENTAL SAVE (Every 5 new cheaters)
                    if current_new > 0 and current_new % 5 == 0:
                        self.save()

                # Add some opponents to queue to keep crawling
                # Limit queue growth
                if len(queue) < 1000:
                    import random
                    # Prioritize recent active players, but random sample is fine
                    queue.extend(random.sample(to_check, min(len(to_check), 10)))

    async def check_chesscom_player_controlled(self, username: str, client: httpx.AsyncClient, sem: asyncio.Semaphore):
        """Check player status with semaphore control."""
        async with sem:
            try:
                resp = await client.get(f"https://api.chess.com/pub/player/{username}", headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    # Check for fair play violation
                    if "fair_play" in status or status == "closed:fair_play_violations":
                        self._add_cheater(
                            username=data["username"],
                            platform="chesscom",
                            title=data.get("title"), # Might be None
                            status=status
                        )
                        print(f"  [!] FOUND: {data.get('title') or ''} {data['username']} ({status})")
            except Exception:
                pass
            finally:
                # Be kind to the API
                await asyncio.sleep(0.05)

    def _add_cheater(self, username: str, platform: str, title: str, status: str):
        if username.lower() not in self.existing_usernames:
            self.cheaters.append({
                "username": username,
                "platform": platform,
                "title": title,
                "status": status,
                "discovered_at": time.time()
            })
            self.existing_usernames.add(username.lower())
    
    def save(self):
        """Save updated list to file."""
        with open(CHEATERS_FILE, "w") as f:
            json.dump({
                "last_updated": time.strftime("%Y-%m-%d"),
                "titled_cheaters": self.cheaters
            }, f, indent=2)
        # print(f"\nSaved {len(self.cheaters)} cheaters to {CHEATERS_FILE}") # Silence spam

async def main():
    discoverer = CheaterDiscoverer()
    try:
        await discoverer.scan_via_crawler(target_new_cheaters=60) # Target 60 total new
    finally:
        print("\nScan finishing/interrupted. Saving final progress...")
        discoverer.save()
        print(f"Final Count: {len(discoverer.cheaters)} cheaters saved.")

if __name__ == "__main__":
    try:
        if asyncio.get_event_loop().is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handled in main finally block if running, but if not:
        pass
    except Exception as e:
         print(f"Error: {e}")
