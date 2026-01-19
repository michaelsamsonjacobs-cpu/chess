"""Quick diagnostic to find the FK error."""
import traceback

try:
    from server.database import Base, engine
    from server.models.game import Game, BatchAnalysis, User
    from server.agents.models import ConnectedAccount, SyncJob, CheatReport, UsageStats
    from server.models.banned_player import BannedPlayer
    
    print("All models imported successfully!")
    print(f"Tables in metadata: {list(Base.metadata.tables.keys())}")
    
    # Try to create tables
    Base.metadata.create_all(bind=engine)
    print("SUCCESS - All tables created!")
    
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
