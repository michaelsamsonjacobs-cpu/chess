
import json
import sys
from pathlib import Path
from typing import List, Dict

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
GAMES_DIR = DATA_DIR / "cheater_games"
RESULTS_FILE = DATA_DIR / "cheater_windowed_analysis.json"

def analyze_windowed_cheating():
    """
    Analyze players for "windowed" cheating patterns using multiple sensitivities.
    """
    configs = [
        {"name": "Conservative", "window": 20, "high_acc": 0.95, "density": 0.3}, # 6/20 perfect
        {"name": "Balanced",     "window": 20, "high_acc": 0.95, "density": 0.2}, # 4/20 perfect
        {"name": "Aggressive",   "window": 20, "high_acc": 0.95, "density": 0.15}, # 3/20 perfect
    ]
    
    # Load all games once
    game_files = list(GAMES_DIR.glob("*.json"))
    print(f"Loaded {len(game_files)} player files.")
    
    player_data = []
    for game_file in game_files:
        username = game_file.stem.split("_")[-1]
        with open(game_file, "r") as f:
            games = json.load(f)
        games.sort(key=lambda g: g.get("end_time", 0))
        
        accuracies = []
        for g in games:
            acc = 0
            if "accuracies" in g:
                white = g.get("white", {}).get("username", "").lower()
                if white == username.lower():
                    acc = g["accuracies"].get("white", 0)
                else:
                    acc = g["accuracies"].get("black", 0)
            if acc > 1.0: acc = acc / 100.0
            accuracies.append(acc)
        player_data.append({"username": username, "accuracies": accuracies, "total": len(games)})
        
    # Run analysis for each config
    for config in configs:
        print(f"\n--- Strategy: {config['name']} (Window {config['window']}, Density {int(config['density']*100)}%) ---")
        flagged = []
        
        window_size = config['window']
        threshold = config['high_acc']
        density_thresh = config['density']
        
        for p in player_data:
            accuracies = p["accuracies"]
            max_d = 0.0
            for i in range(len(accuracies) - window_size + 1):
                window = accuracies[i : i + window_size]
                cnt = sum(1 for a in window if a >= threshold)
                d = cnt / window_size
                if d > max_d: max_d = d
            
            if max_d >= density_thresh:
                flagged.append(f"{p['username']} ({int(max_d*100)}%)")
                
        print(f"Flagged {len(flagged)}/{len(player_data)} players:")
        print(", ".join(flagged))

if __name__ == "__main__":
    analyze_windowed_cheating()
