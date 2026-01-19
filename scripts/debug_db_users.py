
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from server.models.game import User
from sqlalchemy import select

db = SessionLocal()
users = db.execute(select(User).limit(50)).scalars().all()
print(f"Total users found: {len(users)}")
for u in users:
    print(f" - {u.username} (id={u.id})")
db.close()
