
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    print("Importing server.database...")
    from server.database import Base
    print("Importing server.legacy_app_models (Legacy)...")
    import server.legacy_app_models
    print("Legacy models imported.")
    
    print("Importing server.models (New)...")
    import server.models
    import server.models.game
    print("New models imported.")

    print("Tables in Base.metadata:")
    for t in Base.metadata.tables.keys():
        print(f" - {t}")

    print("Re-importing server.app (legacy router)...")
    import server.app
    print("Done.")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
