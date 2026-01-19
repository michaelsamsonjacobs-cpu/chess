
import os
import sys

# Add CWD to path so we can import server
sys.path.append(os.getcwd())

from server.database import DATABASE_URL
print(f"DATABASE_URL: {DATABASE_URL}")
