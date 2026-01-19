
import sys
import os
import traceback

sys.path.append(os.getcwd())

print("--- Starting Diagnosis ---")
try:
    import server.main
    print("SUCCESS: server.main imported")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"OTHER ERROR: {e}")
    traceback.print_exc()
print("--- End Diagnosis ---")
