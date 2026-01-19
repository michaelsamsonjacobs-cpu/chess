
import asyncio
import json
import time
from pathlib import Path
import httpx

DATA_DIR = Path(__file__).parent.parent / "data"
CHEATERS_FILE = DATA_DIR / "known_cheaters.json"

RESTORE_LIST = [
    "bablusut", "vgt187", "ctl77", "adidahottie", "drik", "cubbiesrule81", "domdc", 
    "me_psicho", "belbn", "mikhailtal1705",
    "ammarkefi", "tuyhoaphuyen", "imaroundsound", "rookslovechess", "janjuha95", "windopo", "nik_sk",
    "corvettec5c", "amber_amor", "badridas", "dipender108", "julayvalenciia", "keptosbulves", "thehoudini4", "georgenammour1", "gemayel",
    "quickcastling", "peperruiz", "foldblinded", "bumtaksi", "henb1", "sergey-sdb1", "iiibullet", "asvaria", "blackviper96", "majestra139", "turayev_shahruh7", "mishaban228", "gmczech", "obai1996",
    "ikuusestockfish", "kuoux",
    "akila_dilshan2004"
]

async def restore_cheaters():
    print(f"Restoring {len(RESTORE_LIST)} cheaters from logs...")
    
    # Load existing
    existing_usernames = set()
    current_data = {"last_updated": "", "titled_cheaters": []}
    
    if CHEATERS_FILE.exists():
        with open(CHEATERS_FILE, "r") as f:
            current_data = json.load(f)
            for c in current_data.get("titled_cheaters", []):
                existing_usernames.add(c["username"].lower())
    
    cheaters_list = current_data["titled_cheaters"]
    
    async with httpx.AsyncClient() as client:
        for username in RESTORE_LIST:
            if username.lower() in existing_usernames:
                print(f"Skipping existing: {username}")
                continue
                
            try:
                print(f"Fetching details for {username}...")
                resp = await client.get(f"https://api.chess.com/pub/player/{username}")
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    cheaters_list.append({
                        "username": data["username"],
                        "platform": "chesscom",
                        "title": data.get("title"),
                        "status": status,
                        "restored_from_log": True
                    })
                    print(f"  Restored: {username} ({status})")
                else:
                    print(f"  Failed to fetch {username}: {resp.status_code}")
            except Exception as e:
                print(f"  Error fetching {username}: {e}")
            
            await asyncio.sleep(0.2)
            
    # Save back
    current_data["last_updated"] = time.strftime("%Y-%m-%d")
    current_data["titled_cheaters"] = cheaters_list
    
    with open(CHEATERS_FILE, "w") as f:
        json.dump(current_data, f, indent=2)
    
    print(f"\nSuccessfully saved {len(cheaters_list)} cheaters to {CHEATERS_FILE}")

if __name__ == "__main__":
    asyncio.run(restore_cheaters())
