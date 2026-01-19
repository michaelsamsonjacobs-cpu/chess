"""API Routes for Automated Agents.

Endpoints for:
- Managing connected accounts (Lichess/Chess.com)
- Triggering manual/auto syncs
- Viewing sync status and job history
- Accessing cheat reports
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.database import get_db
from server.agents.models import ConnectedAccount, SyncJob, CheatReport, Platform
from server.agents.game_sync_agent import run_scheduled_sync, GameSyncAgent

router = APIRouter(prefix="/agents", tags=["Agents"])


# --- Pydantic Models ---

class AccountCreate(BaseModel):
    platform: str
    username: str
    access_token: Optional[str] = None
    
class AccountResponse(BaseModel):
    id: int
    platform: str
    username: str
    sync_enabled: bool
    last_synced_at: Optional[datetime]
    token_expired: bool
    
    class Config:
        orm_mode = True

class SyncJobResponse(BaseModel):
    id: int
    status: str
    games_fetched: int
    opponents_flagged: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    
    class Config:
        orm_mode = True

class ReportResponse(BaseModel):
    id: int
    flagged_player: str
    platform: str
    ensemble_score: int
    risk_level: str
    summary: str
    created_at: datetime
    dismissed: bool
    
    class Config:
        orm_mode = True


# --- Account Management ---

@router.get("/accounts", response_model=List[AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    """List all connected accounts."""
    return db.query(ConnectedAccount).all()

@router.post("/accounts", response_model=AccountResponse)
def connect_account(account: AccountCreate, db: Session = Depends(get_db)):
    """Connect a new platform account."""
    # Check if exists
    existing = db.query(ConnectedAccount).filter_by(
        platform=account.platform,
        platform_username=account.username
    ).first()
    
    if existing:
        # Update token if provided
        if account.access_token:
            existing.access_token = account.access_token
            db.commit()
            db.refresh(existing)
        return existing
    
    # Create new
    # Hardcode user_id=1 for single-user desktop app
    new_account = ConnectedAccount(
        user_id=1,
        platform=account.platform,
        platform_username=account.username,
        access_token=account.access_token
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return new_account

@router.delete("/accounts/{account_id}")
def disconnect_account(account_id: int, db: Session = Depends(get_db)):
    """Disconnect an account."""
    account = db.query(ConnectedAccount).get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    db.delete(account)
    db.commit()
    return {"message": "Account disconnected"}

@router.patch("/accounts/{account_id}/sync")
def toggle_sync(account_id: int, enabled: bool, db: Session = Depends(get_db)):
    """Enable or disable auto-sync."""
    account = db.query(ConnectedAccount).get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account.sync_enabled = enabled
    db.commit()
    return {"message": f"Sync {'enabled' if enabled else 'disabled'}"}


# --- Agent Control ---

@router.post("/sync/now")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    account_id: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    """Trigger an immediate sync (background task)."""
    if account_id:
        account = db.query(ConnectedAccount).get(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # We can't pickle the agent easily, so run a lightweight wrapper
        # Ideally this goes to Celery/RQ, here we use FastAPI background tasks
        background_tasks.add_task(run_single_sync_async, account_id)
    else:
        background_tasks.add_task(run_all_syncs_async)
        
    return {"message": "Sync started in background"}

@router.get("/jobs", response_model=List[SyncJobResponse])
def list_jobs(limit: int = 10, db: Session = Depends(get_db)):
    """List recent sync jobs."""
    return db.query(SyncJob).order_by(SyncJob.created_at.desc()).limit(limit).all()


# --- Reports ---

@router.get("/reports", response_model=List[ReportResponse])
def list_reports(
    platform: Optional[str] = None, 
    min_score: int = 0,
    dismissed: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """List cheat detection reports."""
    query = db.query(CheatReport).filter(
        CheatReport.ensemble_score >= min_score,
        CheatReport.dismissed == dismissed
    )
    
    if platform:
        query = query.filter(CheatReport.platform == platform)
        
    return query.order_by(CheatReport.created_at.desc()).limit(limit).all()

@router.post("/reports/{report_id}/dismiss")
def dismiss_report(report_id: int, reason: Optional[str] = None, db: Session = Depends(get_db)):
    """Dismiss a report (false positive)."""
    report = db.query(CheatReport).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report.dismissed = True
    report.dismissed_reason = reason
    db.commit()
    return {"message": "Report dismissed"}


# --- Async Helpers ---

async def run_single_sync_async(account_id: int):
    """Wrapper to run sync in new session."""
    with next(get_db()) as db:
        agent = GameSyncAgent(db)
        account = db.query(ConnectedAccount).get(account_id)
        if account:
            await agent.sync_account(account)

async def run_all_syncs_async():
    """Wrapper to run all syncs."""
    with next(get_db()) as db:
        agent = GameSyncAgent(db)
        await agent.sync_all_enabled()
