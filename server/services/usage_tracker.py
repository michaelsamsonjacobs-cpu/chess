"""Usage tracking service for rate limiting game analysis."""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from server.agents.models import UsageStats, SubscriptionTier, TIER_LIMITS


class UsageTracker:
    """Service for tracking and enforcing usage limits."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_stats(self, user_id: int) -> UsageStats:
        """Get or create usage stats for a user."""
        stats = self.db.query(UsageStats).filter(
            UsageStats.user_id == user_id
        ).first()
        
        if not stats:
            stats = UsageStats(
                user_id=user_id,
                period_start=datetime.utcnow(),
                games_analyzed=0,
                tier=SubscriptionTier.FREE_TRIAL.value,
                trial_ends_at=datetime.utcnow() + timedelta(days=3),
            )
            self.db.add(stats)
            self.db.commit()
            self.db.refresh(stats)
        
        # Check if we need to reset for a new month
        self._maybe_reset_period(stats)
        
        return stats
    
    def _maybe_reset_period(self, stats: UsageStats) -> None:
        """Reset usage counter if we're in a new billing period (monthly)."""
        if not stats.period_start:
            stats.period_start = datetime.utcnow()
            stats.games_analyzed = 0
            self.db.commit()
            return
        
        now = datetime.utcnow()
        period_end = stats.period_start + timedelta(days=30)
        
        if now >= period_end:
            stats.period_start = now
            stats.games_analyzed = 0
            self.db.commit()
    
    def check_limit(self, user_id: int) -> Tuple[bool, UsageStats]:
        """
        Check if user can analyze more games.
        
        Returns:
            Tuple of (can_proceed: bool, stats: UsageStats)
        """
        stats = self.get_or_create_stats(user_id)
        
        # Check if trial expired and not subscribed
        if stats.tier == SubscriptionTier.FREE_TRIAL.value:
            if stats.trial_ends_at and datetime.utcnow() > stats.trial_ends_at:
                if stats.subscription_status != "active":
                    return False, stats
        
        return not stats.is_limit_reached, stats
    
    def increment_usage(self, user_id: int, count: int = 1) -> UsageStats:
        """Increment the games analyzed counter."""
        stats = self.get_or_create_stats(user_id)
        stats.games_analyzed += count
        stats.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(stats)
        return stats
    
    def upgrade_tier(self, user_id: int, new_tier: SubscriptionTier, 
                     stripe_customer_id: Optional[str] = None,
                     stripe_subscription_id: Optional[str] = None) -> UsageStats:
        """Upgrade a user's subscription tier."""
        stats = self.get_or_create_stats(user_id)
        stats.tier = new_tier.value
        stats.subscription_status = "active"
        
        if stripe_customer_id:
            stats.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id:
            stats.stripe_subscription_id = stripe_subscription_id
        
        self.db.commit()
        self.db.refresh(stats)
        return stats
    
    def get_usage_summary(self, user_id: int) -> dict:
        """Get a summary of user's usage for UI display."""
        stats = self.get_or_create_stats(user_id)
        return stats.to_dict()


def check_usage_limit(db: Session, user_id: int) -> Tuple[bool, dict]:
    """
    Convenience function used by API routes.
    
    Returns:
        Tuple of (can_proceed: bool, usage_info: dict)
    """
    tracker = UsageTracker(db)
    can_proceed, stats = tracker.check_limit(user_id)
    return can_proceed, stats.to_dict()


def increment_usage(db: Session, user_id: int, count: int = 1) -> dict:
    """Convenience function to increment usage from API routes."""
    tracker = UsageTracker(db)
    stats = tracker.increment_usage(user_id, count)
    return stats.to_dict()
