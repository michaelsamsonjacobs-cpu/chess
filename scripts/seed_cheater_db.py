
import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database import SessionLocal
from server.services.cheater_db import add_banned_player

DATA_DIR = Path(__file__).parent.parent / "data"
CHEATERS_FILE = DATA_DIR / "known_cheaters.json"

def seed_cheaters():
    print(f"Seeding known cheaters from {CHEATERS_FILE}...")
    
    if not CHEATERS_FILE.exists():
        print("Error: known_cheaters.json not found!")
        return

    with open(CHEATERS_FILE, "r") as f:
        data = json.load(f)
        
    titled_cheaters = data.get("titled_cheaters", [])
    
    db = SessionLocal()
    count = 0
    try:
        for cheater in titled_cheaters:
            username = cheater["username"]
            platform = cheater["platform"]
            status = cheater.get("status", "unknown")
            
            # Determine ban type
            ban_type = "fair_play_violation" if "fair_play" in status else "closed"
            
            add_banned_player(
                db=db,
                username=username,
                platform=platform,
                ban_type=ban_type,
                source="manual_research_list",
                ban_reason=status
            )
            count += 1
            print(f"  Added/Updated: {username} ({platform})")
            
        db.commit()
        print(f"\nSuccessfully seeded {count} cheaters into database.")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_cheaters()
