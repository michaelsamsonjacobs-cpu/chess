"""
Fetch and analyze games from known titled cheaters.
This script collects game data and runs analysis to identify cheating patterns.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
CHEATERS_FILE = DATA_DIR / "known_cheaters.json"
GAMES_DIR = DATA_DIR / "cheater_games"
RESULTS_FILE = DATA_DIR / "cheater_analysis_results.json"

# Rate limiting
CHESSCOM_DELAY = 6  # seconds between requests (10 req/min limit)
LICHESS_DELAY = 2   # seconds between requests (30 req/min limit)


class CheaterGameFetcher:
    """Fetch games from known cheaters on Chess.com and Lichess."""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "ChessGuard/1.0 (research@chessguard.dev)"
        }
        self.results: Dict[str, Any] = {}
        
    async def fetch_chesscom_games(self, username: str, max_months: int = 2, max_games: int = 100) -> List[Dict]:
        """Fetch games from Chess.com for a given username."""
        games = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get archives
            try:
                archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
                resp = await client.get(archives_url, headers=self.headers)
                if resp.status_code != 200:
                    print(f"  [!] Could not fetch archives for {username}: {resp.status_code}")
                    return []
                    
                archives = resp.json().get("archives", [])
                # Get most recent months
                recent_archives = archives[-max_months:] if len(archives) > max_months else archives
                
                # Fetch in reverse order (newest first) to hit game limit faster
                for archive_url in reversed(recent_archives):
                    if len(games) >= max_games:
                        break
                        
                    await asyncio.sleep(CHESSCOM_DELAY)  # Rate limiting
                    try:
                        resp = await client.get(archive_url, headers=self.headers)
                        if resp.status_code == 200:
                            archive_games = resp.json().get("games", [])
                            # Archives are usually chronological, so reversing them gets newest first
                            archive_games.reverse()
                            
                            needed = max_games - len(games)
                            games.extend(archive_games[:needed])
                            
                            print(f"    Fetched {len(archive_games[:needed])} games from {archive_url.split('/')[-2]}/{archive_url.split('/')[-1]}")
                    except Exception as e:
                        print(f"  [!] Error fetching archive: {e}")
                        continue
                        
            except Exception as e:
                print(f"  [!] Error fetching {username}: {e}")
                
        return games
    
    async def fetch_lichess_games(self, username: str, max_games: int = 500) -> List[Dict]:
        """Fetch games from Lichess for a given username."""
        games = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                url = f"https://lichess.org/api/games/user/{username}"
                headers = {**self.headers, "Accept": "application/x-ndjson"}
                params = {"max": max_games, "pgnInJson": "true"}
                
                async with client.stream("GET", url, headers=headers, params=params) as resp:
                    if resp.status_code != 200:
                        print(f"  [!] Could not fetch games for {username}: {resp.status_code}")
                        return []
                        
                    async for line in resp.aiter_lines():
                        if line.strip():
                            games.append(json.loads(line))
                            
            except Exception as e:
                print(f"  [!] Error fetching Lichess games for {username}: {e}")
                
        return games
    
    def analyze_game_patterns(self, games: List[Dict], platform: str) -> Dict[str, Any]:
        """Analyze patterns in a set of games."""
        if not games:
            return {"error": "No games to analyze"}
        
        analysis = {
            "total_games": len(games),
            "time_controls": {},
            "results": {"wins": 0, "losses": 0, "draws": 0},
            "accuracy_data": [],
            "rating_range": {"min": float("inf"), "max": 0},
            "openings": {},
        }
        
        for game in games:
            # Time control distribution
            if platform == "chesscom":
                tc = game.get("time_class", "unknown")
                rating_field = "white" if game.get("white", {}).get("username", "").lower() else "black"
            else:  # lichess
                tc = game.get("speed", "unknown")
                
            analysis["time_controls"][tc] = analysis["time_controls"].get(tc, 0) + 1
            
            # Results (Chess.com format)
            if platform == "chesscom":
                # Determine if this player won/lost/drew
                white = game.get("white", {})
                black = game.get("black", {})
                white_result = white.get("result", "")
                
                if "win" in white_result.lower():
                    analysis["results"]["wins"] += 1
                elif "draw" in white_result.lower() or "stalemate" in white_result.lower():
                    analysis["results"]["draws"] += 1
                else:
                    analysis["results"]["losses"] += 1
                    
                # Accuracy if available
                if "accuracies" in game:
                    acc = game["accuracies"]
                    if "white" in acc:
                        analysis["accuracy_data"].append(acc["white"])
                    if "black" in acc:
                        analysis["accuracy_data"].append(acc["black"])
                        
                # Rating tracking
                for color in ["white", "black"]:
                    rating = game.get(color, {}).get("rating", 0)
                    if rating:
                        analysis["rating_range"]["min"] = min(analysis["rating_range"]["min"], rating)
                        analysis["rating_range"]["max"] = max(analysis["rating_range"]["max"], rating)
                        
            # Lichess format
            else:
                winner = game.get("winner")
                if winner == "white":
                    analysis["results"]["wins"] += 1
                elif winner == "black":
                    analysis["results"]["losses"] += 1
                else:
                    analysis["results"]["draws"] += 1
        
        # Calculate derived stats
        total = analysis["total_games"]
        if total > 0:
            analysis["win_rate"] = round(analysis["results"]["wins"] / total * 100, 1)
            
        if analysis["accuracy_data"]:
            analysis["avg_accuracy"] = round(sum(analysis["accuracy_data"]) / len(analysis["accuracy_data"]), 1)
            analysis["max_accuracy"] = max(analysis["accuracy_data"])
            analysis["high_accuracy_games"] = len([a for a in analysis["accuracy_data"] if a >= 95])
            
        if analysis["rating_range"]["min"] == float("inf"):
            analysis["rating_range"] = {"min": 0, "max": 0}
            
        return analysis
    
    async def process_all_cheaters(self):
        """Process all known cheaters from the database."""
        # Load known cheaters
        with open(CHEATERS_FILE, "r") as f:
            data = json.load(f)
            
        titled_cheaters = data.get("titled_cheaters", [])
        print(f"\n{'='*60}")
        print(f"CHEATER GAME ANALYSIS - {len(titled_cheaters)} Titled Players")
        print(f"{'='*60}\n")
        
        # Ensure games directory exists
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
        
        all_results = {
            "timestamp": datetime.now().isoformat(),
            "total_players": len(titled_cheaters),
            "players": {}
        }
        
        for i, cheater in enumerate(titled_cheaters, 1):
            username = cheater["username"]
            title = cheater["title"]
            platform = cheater["platform"]
            name = cheater.get("name", "Unknown")
            
            print(f"[{i}/{len(titled_cheaters)}] {title} {username} ({name})")
            print(f"  Platform: {platform}")
            
            # Check if we already have games saved
            games_file = GAMES_DIR / f"{platform}_{username}.json"
            
            if games_file.exists():
                print(f"  Loading cached games...")
                with open(games_file, "r") as f:
                    games = json.load(f)
            else:
                # Fetch games
                print(f"  Fetching games...")
                if platform == "chesscom":
                    games = await self.fetch_chesscom_games(username)
                else:
                    games = await self.fetch_lichess_games(username)
                    
                # Save games
                if games:
                    with open(games_file, "w") as f:
                        json.dump(games, f)
                    print(f"  Saved {len(games)} games to {games_file.name}")
            
            # Analyze patterns
            print(f"  Analyzing patterns...")
            analysis = self.analyze_game_patterns(games, platform)
            
            all_results["players"][username] = {
                "title": title,
                "platform": platform,
                "name": name,
                "games_count": len(games),
                "analysis": analysis
            }
            
            # Print summary
            print(f"  Games: {analysis.get('total_games', 0)}")
            print(f"  Win Rate: {analysis.get('win_rate', 'N/A')}%")
            if "avg_accuracy" in analysis:
                print(f"  Avg Accuracy: {analysis['avg_accuracy']}%")
                print(f"  High Accuracy Games (≥95%): {analysis.get('high_accuracy_games', 0)}")
            print()
            
            # Small delay between players
            await asyncio.sleep(1)
        
        # Save all results
        with open(RESULTS_FILE, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n{'='*60}")
        print(f"Results saved to {RESULTS_FILE}")
        print(f"{'='*60}")
        
        # Generate summary
        self.generate_summary(all_results)
        
        return all_results
    
    def generate_summary(self, results: Dict):
        """Generate a summary of cheater patterns."""
        print("\n" + "="*60)
        print("CHEATER PATTERN SUMMARY")
        print("="*60 + "\n")
        
        total_games = 0
        all_accuracies = []
        all_win_rates = []
        high_acc_totals = 0
        
        by_title = {}
        
        for username, data in results["players"].items():
            title = data["title"]
            analysis = data["analysis"]
            
            if title not in by_title:
                by_title[title] = {"count": 0, "games": 0, "accuracies": [], "win_rates": []}
                
            by_title[title]["count"] += 1
            by_title[title]["games"] += analysis.get("total_games", 0)
            
            if "avg_accuracy" in analysis:
                by_title[title]["accuracies"].append(analysis["avg_accuracy"])
                all_accuracies.append(analysis["avg_accuracy"])
                
            if "win_rate" in analysis:
                by_title[title]["win_rates"].append(analysis["win_rate"])
                all_win_rates.append(analysis["win_rate"])
                
            if "high_accuracy_games" in analysis:
                high_acc_totals += analysis["high_accuracy_games"]
                
            total_games += analysis.get("total_games", 0)
        
        print(f"Total Players Analyzed: {len(results['players'])}")
        print(f"Total Games Collected: {total_games}")
        print(f"Games with ≥95% Accuracy: {high_acc_totals}")
        print()
        
        if all_accuracies:
            print(f"Overall Avg Accuracy: {sum(all_accuracies)/len(all_accuracies):.1f}%")
        if all_win_rates:
            print(f"Overall Avg Win Rate: {sum(all_win_rates)/len(all_win_rates):.1f}%")
        print()
        
        print("BY TITLE:")
        for title in ["GM", "IM", "FM", "CM", "NM"]:
            if title in by_title:
                t = by_title[title]
                avg_acc = sum(t["accuracies"])/len(t["accuracies"]) if t["accuracies"] else 0
                avg_wr = sum(t["win_rates"])/len(t["win_rates"]) if t["win_rates"] else 0
                print(f"  {title}: {t['count']} players, {t['games']} games, {avg_acc:.1f}% avg accuracy, {avg_wr:.1f}% win rate")


async def main():
    fetcher = CheaterGameFetcher()
    await fetcher.process_all_cheaters()


if __name__ == "__main__":
    asyncio.run(main())
