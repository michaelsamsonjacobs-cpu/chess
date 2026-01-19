
import sys
import os
import traceback

sys.path.append(os.getcwd())

print("--- Testing Agent Models Import ---")
try:
    from server.agents.models import ConnectedAccount
    print("SUCCESS: ConnectedAccount imported")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
