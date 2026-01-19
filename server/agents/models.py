"""Connected Account management for OAuth tokens."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from server.database import Base


class Platform(str, Enum):
    """Supported chess platforms."""
    LICHESS = "lichess"
    CHESSCOM = "chesscom"


class ConnectedAccount(Base):
    """OAuth-connected platform accounts for automatic game syncing."""
    
    __tablename__ = "connected_accounts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users_v2.id"), nullable=False)
    
    # Platform info
    platform = Column(String(20), nullable=False)  # 'lichess' | 'chesscom'
    platform_username = Column(String(100))
    platform_user_id = Column(String(100))
    
    # OAuth tokens (encrypted at rest in production)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # Sync settings
    sync_enabled = Column(Boolean, default=True)
    last_synced_at = Column(DateTime)
    last_game_timestamp = Column(DateTime)  # Track for incremental sync
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="connected_accounts")
    sync_jobs = relationship("SyncJob", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ConnectedAccount {self.platform}:{self.platform_username}>"
    
    @property
    def is_token_expired(self) -> bool:
        """Check if OAuth token is expired."""
        if not self.token_expires_at:
            return False
        return datetime.utcnow() > self.token_expires_at
    
    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "username": self.platform_username,
            "sync_enabled": self.sync_enabled,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "token_expired": self.is_token_expired,
        }


class SyncJob(Base):
    """Track sync job execution history."""
    
    __tablename__ = "sync_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("connected_accounts.id"), nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    
    # Stats
    games_fetched = Column(Integer, default=0)
    games_analyzed = Column(Integer, default=0)
    opponents_checked = Column(Integer, default=0)
    opponents_flagged = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Error tracking
    error_message = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    account = relationship("ConnectedAccount", back_populates="sync_jobs")
    
    def __repr__(self):
        return f"<SyncJob {self.id}: {self.status}>"
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "games_fetched": self.games_fetched,
            "games_analyzed": self.games_analyzed,
            "opponents_flagged": self.opponents_flagged,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error_message,
        }


class CheatReport(Base):
    """Generated cheat detection reports for flagged players."""
    
    __tablename__ = "cheat_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users_v2.id"), nullable=False)
    
    # Flagged player info
    flagged_player = Column(String(100), nullable=False)
    platform = Column(String(20), nullable=False)
    
    # Detection results
    ensemble_score = Column(Integer)  # 0-100
    risk_level = Column(String(20))   # LOW, MODERATE, HIGH, CRITICAL
    
    # Report content
    summary_text = Column(Text)       # Plain-English explanation
    full_report_json = Column(Text)   # Detailed JSON data
    pdf_path = Column(String(255))    # Path to generated PDF
    
    # Stats
    games_analyzed = Column(Integer, default=0)
    
    # User feedback
    dismissed = Column(Boolean, default=False)
    dismissed_reason = Column(String(255))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="cheat_reports")
    
    def __repr__(self):
        return f"<CheatReport {self.id}: {self.flagged_player} ({self.risk_level})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "flagged_player": self.flagged_player,
            "platform": self.platform,
            "ensemble_score": self.ensemble_score,
            "risk_level": self.risk_level,
            "summary": self.summary_text,
            "games_analyzed": self.games_analyzed,
            "dismissed": self.dismissed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SubscriptionTier(str, Enum):
    """User subscription tiers with different limits."""
    FREE_TRIAL = "free_trial"
    STANDARD = "standard"      # $9.95/mo - 500 games/month
    PRO = "pro"                # $29.95/mo - 2000 games/month
    UNLIMITED = "unlimited"    # Custom pricing


# Limits per tier (games per month)
TIER_LIMITS = {
    SubscriptionTier.FREE_TRIAL: 50,
    SubscriptionTier.STANDARD: 500,
    SubscriptionTier.PRO: 2000,
    SubscriptionTier.UNLIMITED: 999999,
}


class UsageStats(Base):
    """Track user's monthly usage for rate limiting."""
    
    __tablename__ = "usage_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users_v2.id"), nullable=False, unique=True)
    
    # Current period
    period_start = Column(DateTime, default=datetime.utcnow)
    games_analyzed = Column(Integer, default=0)
    
    # Subscription tier
    tier = Column(String(20), default=SubscriptionTier.FREE_TRIAL.value)
    
    # Stripe info
    stripe_customer_id = Column(String(100))
    stripe_subscription_id = Column(String(100))
    subscription_status = Column(String(20), default="trialing")  # trialing, active, canceled
    trial_ends_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="usage_stats")
    
    def __repr__(self):
        return f"<UsageStats user={self.user_id} used={self.games_analyzed}/{self.monthly_limit}>"
    
    @property
    def monthly_limit(self) -> int:
        """Get the monthly game limit based on tier."""
        try:
            return TIER_LIMITS[SubscriptionTier(self.tier)]
        except (ValueError, KeyError):
            return TIER_LIMITS[SubscriptionTier.FREE_TRIAL]
    
    @property
    def games_remaining(self) -> int:
        """Calculate remaining games for this period."""
        return max(0, self.monthly_limit - self.games_analyzed)
    
    @property
    def usage_percentage(self) -> float:
        """Calculate usage as a percentage."""
        if self.monthly_limit == 0:
            return 100.0
        return min(100.0, (self.games_analyzed / self.monthly_limit) * 100)
    
    @property
    def is_limit_reached(self) -> bool:
        """Check if user has hit their monthly limit."""
        return self.games_analyzed >= self.monthly_limit
    
    def to_dict(self):
        return {
            "games_analyzed": self.games_analyzed,
            "monthly_limit": self.monthly_limit,
            "games_remaining": self.games_remaining,
            "usage_percentage": round(self.usage_percentage, 1),
            "tier": self.tier,
            "subscription_status": self.subscription_status,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
        }

