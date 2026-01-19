"""Background job scheduler for automated game syncing."""

import logging
from datetime import datetime, timedelta
from typing import Optional

LOGGER = logging.getLogger(__name__)

# Try to import APScheduler (lightweight alternative to Celery)
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_SCHEDULER = True
except ImportError:
    LOGGER.warning("APScheduler not installed. Run: pip install apscheduler")
    HAS_SCHEDULER = False


class BackgroundScheduler:
    """Manages background jobs for Chess Observer."""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
    
    def start(self):
        """Start the background scheduler."""
        if not HAS_SCHEDULER:
            LOGGER.warning("Scheduler not available - background jobs disabled")
            return
        
        if self._running:
            LOGGER.info("Scheduler already running")
            return
        
        self.scheduler = AsyncIOScheduler()
        
        # Add jobs
        self.scheduler.add_job(
            self._sync_all_accounts,
            trigger=IntervalTrigger(hours=6),
            id="sync_all_accounts",
            name="Sync all connected accounts",
            replace_existing=True,
        )
        
        self.scheduler.add_job(
            self._cleanup_old_jobs,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_old_jobs",
            name="Clean up old sync jobs",
            replace_existing=True,
        )
        
        self.scheduler.add_job(
            self._reset_monthly_usage,
            trigger=IntervalTrigger(days=1),
            id="reset_monthly_usage",
            name="Reset monthly usage counters",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self._running = True
        LOGGER.info("Background scheduler started with 3 jobs")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler and self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            LOGGER.info("Background scheduler stopped")
    
    async def _sync_all_accounts(self):
        """Sync games for all connected accounts."""
        LOGGER.info("Starting scheduled sync for all accounts...")
        
        try:
            from server.database import SessionLocal
            from server.agents.models import ConnectedAccount
            from server.agents.game_sync_agent import GameSyncAgent
            
            db = SessionLocal()
            try:
                accounts = db.query(ConnectedAccount).filter(
                    ConnectedAccount.sync_enabled == True
                ).all()
                
                LOGGER.info(f"Found {len(accounts)} accounts to sync")
                
                for account in accounts:
                    try:
                        agent = GameSyncAgent(db, account.user_id)
                        await agent.sync_account(account.id)
                        LOGGER.info(f"Synced account {account.platform}:{account.platform_username}")
                    except Exception as e:
                        LOGGER.error(f"Failed to sync account {account.id}: {e}")
                        continue
                        
            finally:
                db.close()
                
        except Exception as e:
            LOGGER.error(f"Scheduled sync failed: {e}")
    
    async def _cleanup_old_jobs(self):
        """Clean up sync jobs older than 30 days."""
        LOGGER.info("Cleaning up old sync jobs...")
        
        try:
            from server.database import SessionLocal
            from server.agents.models import SyncJob
            
            db = SessionLocal()
            try:
                cutoff = datetime.utcnow() - timedelta(days=30)
                deleted = db.query(SyncJob).filter(
                    SyncJob.created_at < cutoff
                ).delete()
                db.commit()
                LOGGER.info(f"Deleted {deleted} old sync jobs")
            finally:
                db.close()
                
        except Exception as e:
            LOGGER.error(f"Cleanup failed: {e}")
    
    async def _reset_monthly_usage(self):
        """Reset usage counters for users whose billing period has ended."""
        LOGGER.info("Checking for monthly usage resets...")
        
        try:
            from server.database import SessionLocal
            from server.agents.models import UsageStats
            
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                thirty_days_ago = now - timedelta(days=30)
                
                # Find usage stats where period started > 30 days ago
                stats_to_reset = db.query(UsageStats).filter(
                    UsageStats.period_start < thirty_days_ago
                ).all()
                
                for stats in stats_to_reset:
                    stats.period_start = now
                    stats.games_analyzed = 0
                    LOGGER.info(f"Reset usage for user {stats.user_id}")
                
                db.commit()
                LOGGER.info(f"Reset usage for {len(stats_to_reset)} users")
                
            finally:
                db.close()
                
        except Exception as e:
            LOGGER.error(f"Usage reset failed: {e}")


# Global scheduler instance
background_scheduler = BackgroundScheduler()


def start_scheduler():
    """Convenience function to start the scheduler."""
    background_scheduler.start()


def stop_scheduler():
    """Convenience function to stop the scheduler."""
    background_scheduler.stop()
