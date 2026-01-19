
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from server.database import SessionLocal
from server.models.banned_player import BannedPlayer

def check_banned():
    db = SessionLocal()
    user = db.execute(select(BannedPlayer).where(BannedPlayer.username == "penguingim1")).scalar_one_or_none()
    
    if user:
        print(f"FOUND IN BAN LIST!")
        print(f"Username: {user.username}")
        print(f"Platform: {user.platform}")
        print(f"Reason: {user.ban_reason}")
        print(f"Source: {user.source}")
    else:
        print("Not found in ban list.")

if __name__ == "__main__":
    check_banned()
