
import sys
import os
import traceback

# Add current dir to sys.path
sys.path.append(os.getcwd())

print("--- Debugging Imports ---")

print("1. Importing server.database")
try:
    import server.database
    print("   SUCCESS")
except Exception:
    traceback.print_exc()

print("\n2. Importing server.services.cheater_db")
try:
    import server.services.cheater_db
    print("   SUCCESS")
except Exception:
    traceback.print_exc()

print("\n3. Importing server.main")
try:
    import server.main
    print("   SUCCESS")
except Exception:
    traceback.print_exc()
