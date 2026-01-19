# ChessGuard Automated Cheat Detection Agent PRD

## 1. Overview

The Automated Cheat Detection Agent extends ChessGuard with intelligent, hands-off monitoring of Chess.com and Lichess accounts. Users connect their accounts via OAuth, and the agent autonomously fetches new games on a configurable schedule (daily/weekly), runs the full detection pipeline, flags suspicious players, and generates human-readable reports explaining why someone may be cheating.

### Vision
Transform ChessGuard from a reactive investigation tool into a proactive guardian that continuously watches for fair-play violations across a user's opponent pool without manual intervention.

---

## 2. Objectives & Success Metrics

| Objective | Metric | Target |
|-----------|--------|--------|
| **Autonomous Coverage** | Games analyzed per user/day | ≥50 games |
| **Detection Quality** | False positive rate on flagged accounts | <5% |
| **Report Clarity** | User comprehension score (survey) | ≥4.5/5 |
| **User Adoption** | Monthly active connected accounts | 100 by Q2 |
| **Operational SLA** | Time from game played to report ready | <24 hours |

---

## 3. Target Users & Use Cases

### 3.1 Primary Users

| User | Need | Value |
|------|------|-------|
| **Competitive Players** | Know if past opponents were cheating | Confidence in results |
| **Content Creators** | Automated monitoring of stream snipers | Protect reputation |
| **Coaches/Teams** | Monitor students' opponents | Fair training environment |
| **Tournament Organizers** | Automated pre-screening | Clean events |

### 3.2 Key Use Cases

1. **Daily Digest**: User wakes up to a summary email/notification listing any new suspicious opponents from yesterday's games.
2. **Opponent Watchlist**: When a flagged player appears in future games, user gets immediate alert.
3. **Evidence Export**: Generate PDF/JSON reports for disputes or platform reports.
4. **Historical Sweep**: On first connection, analyze last 30-90 days of games to identify past cheaters.

---

## 4. Functional Requirements

### 4.1 Account Connection & OAuth

| Requirement | Details |
|-------------|---------|
| **Lichess OAuth** | Use existing `/api/lichess/` OAuth flow; request `game:read` + `preference:read` scopes |
| **Chess.com OAuth** | Implement Chess.com OAuth 2.0 (or API key fallback for public data) |
| **Token Storage** | Encrypted at-rest in `users` table; auto-refresh on expiry |
| **Multi-Account** | Support connecting both platforms per user |
| **Disconnection** | User can revoke via settings; tokens purged immediately |

### 4.2 Game Fetching Agent

| Requirement | Details |
|-------------|---------|
| **Scheduled Sync** | Configurable cron (default: daily 03:00 UTC) |
| **Incremental Fetch** | Track `last_synced_at` per account; fetch only new games |
| **Rate Limiting** | Respect API limits (Lichess: 15 req/min, Chess.com: ~300/hour) |
| **Retry Logic** | Exponential backoff on 429/5xx; max 3 retries |
| **Filtering** | Skip casual/unlimited games unless user opts in; focus on rated games |

### 4.3 Automated Analysis Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Game Fetch  │────▶│ PGN Ingest   │────▶│ Detection    │────▶│ Report Gen   │
│   (Agent)    │     │  Pipeline    │     │  Ensemble    │     │  (Summary)   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
        │                   │                    │                    │
        ▼                   ▼                    ▼                    ▼
   ┌─────────┐        ┌──────────┐         ┌──────────┐        ┌───────────┐
   │Lichess/ │        │GameTable │         │Signals   │        │Cheater    │
   │Chess.com│        │Database  │         │EnsembleDB│        │Reports DB │
   └─────────┘        └──────────┘         └──────────┘        └───────────┘
```

| Stage | Existing Service | Enhancement Needed |
|-------|------------------|-------------------|
| PGN Ingest | `GameAnalysisPipeline.ingest_game()` | Batch mode for bulk import |
| Engine Analysis | `GameAnalysisPipeline.run_analysis()` | Queue-based parallel processing |
| Signal Extraction | `DetectionSignals` + ensemble | Aggregate by opponent player |
| Opponent Flagging | `calculate_ensemble_score()` | Per-opponent score aggregation |

### 4.4 Player Flagging Logic

```python
# Pseudocode for flagging decision
def should_flag_player(opponent_games: List[GameAnalysis]) -> FlagDecision:
    signals = combine_game_signals([g.signals for g in opponent_games])
    result = calculate_ensemble_score(signals)
    
    if result.risk_level in ["HIGH", "CRITICAL"]:
        return FlagDecision(
            flagged=True,
            confidence=result.confidence,
            reason=generate_explanation(result),
            games=opponent_games
        )
    return FlagDecision(flagged=False)
```

**Thresholds (calibrated from 24 titled cheater dataset):**

| Risk Level | Ensemble Score | Action |
|------------|----------------|--------|
| CRITICAL | ≥0.85 | Flag + Priority Alert |
| HIGH | 0.70–0.84 | Flag + Include in Report |
| MODERATE | 0.50–0.69 | Watchlist (no flag) |
| LOW | <0.50 | Clean |

### 4.5 Report Generation

#### 4.5.1 Automated Daily Summary

Content includes:
- Total games synced since last report
- New opponents analyzed
- Flagged accounts (if any) with one-liner reasons
- Link to full evidence report

#### 4.5.2 Per-Player Evidence Report

Extend existing `EvidenceReport` class with:

| Section | Content |
|---------|---------|
| **Executive Summary** | 2-3 sentence verdict with confidence level |
| **Why We Think They Cheated** | Plain-English explanation of top 3 signals |
| **Statistical Evidence** | Engine agreement %, timing anomalies, streak improbability |
| **Game-by-Game Breakdown** | Flagged games with specific suspicious moves highlighted |
| **Comparison to Peers** | "This player's 94% engine agreement is 2σ above GM average" |
| **Recommendation** | "Report to platform" / "Monitor further" / "Likely clean" |

#### 4.5.3 Report Formats

- **PDF**: For sharing/filing disputes
- **JSON**: For API consumers / platform integrations
- **Email Digest**: HTML summary with link to dashboard

### 4.6 Notification System

| Channel | Trigger | Content |
|---------|---------|---------|
| **Email** | Daily (if new flags) | Digest summary |
| **In-App** | Real-time | Badge on dashboard |
| **Webhook** | On flag (opt-in) | JSON payload for Discord/Slack |

---

## 5. System Architecture

### 5.1 New Components

```
server/
├── agents/
│   ├── __init__.py
│   ├── game_sync_agent.py      # Scheduled game fetcher
│   ├── analysis_worker.py      # Background analysis processor
│   └── report_generator.py     # Automated report builder
├── services/
│   ├── opponent_aggregator.py  # Group games by opponent
│   └── explanation_engine.py   # NLG for report summaries
├── api/
│   ├── account_routes.py       # Connect/disconnect accounts
│   ├── agent_routes.py         # Agent status/config endpoints
│   └── report_routes.py        # Fetch/download reports
└── models/
    ├── connected_account.py    # OAuth token storage
    ├── sync_job.py             # Job tracking
    └── cheat_report.py         # Generated report storage
```

### 5.2 Database Schema Additions

```sql
-- Connected platform accounts
CREATE TABLE connected_accounts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    platform VARCHAR(20) NOT NULL,  -- 'lichess' | 'chesscom'
    platform_username VARCHAR(100),
    access_token TEXT ENCRYPTED,
    refresh_token TEXT ENCRYPTED,
    token_expires_at TIMESTAMP,
    last_synced_at TIMESTAMP,
    sync_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sync job history
CREATE TABLE sync_jobs (
    id INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES connected_accounts(id),
    status VARCHAR(20),  -- 'pending' | 'running' | 'completed' | 'failed'
    games_fetched INTEGER,
    games_analyzed INTEGER,
    opponents_flagged INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Generated cheat reports
CREATE TABLE cheat_reports (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    flagged_player VARCHAR(100),
    platform VARCHAR(20),
    ensemble_score FLOAT,
    risk_level VARCHAR(20),
    summary_text TEXT,
    full_report_json JSONB,
    pdf_path VARCHAR(255),
    games_analyzed INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.3 Background Job System

**Option A: Celery + Redis (recommended for scale)**
```python
# agents/game_sync_agent.py
from celery import Celery
from celery.schedules import crontab

app = Celery('chessguard')

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(hour=3, minute=0),  # Daily at 3 AM UTC
        sync_all_accounts.s()
    )

@app.task
def sync_all_accounts():
    accounts = get_enabled_accounts()
    for account in accounts:
        sync_account.delay(account.id)

@app.task
def sync_account(account_id: int):
    account = get_account(account_id)
    games = fetch_new_games(account)
    for game in games:
        analyze_game.delay(game.id, opponent_mode=True)
```

**Option B: APScheduler (simpler, single-process)**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(sync_all_accounts, 'cron', hour=3)
```

---

## 6. Explanation Engine

The most critical differentiator: **explain WHY we think someone is cheating in plain English**.

### 6.1 Explanation Templates

```python
EXPLANATION_TEMPLATES = {
    "engine_agreement_high": (
        "{player} matched the engine's top choice {agreement}% of the time "
        "across {games} games. This is significantly higher than the expected "
        "{expected}% for players rated {rating}. In critical positions where "
        "the best move wasn't obvious, they still found it {critical_pct}% of the time."
    ),
    "timing_anomaly": (
        "Move timing patterns are unusual: {player} spent an average of {avg_time} "
        "seconds per move with suspiciously low variance (CV={cv}). Complex positions "
        "were solved as quickly as simple ones, unlike typical human play."
    ),
    "streak_improbability": (
        "Between {start_date} and {end_date}, {player} achieved a win streak "
        "that has a probability of {prob} under normal conditions. Even accounting "
        "for hot streaks, this performance is a statistical outlier."
    ),
    "critical_accuracy_spike": (
        "In positions where one wrong move loses the game, {player} found the "
        "winning move {critical_correct}/{critical_total} times ({pct}%). This "
        "'sniper' pattern—ordinary play punctuated by perfect critical moves—is "
        "a hallmark of selective engine use."
    )
}
```

### 6.2 Composite Explanation Generator

```python
def generate_explanation(signals: DetectionSignals, result: EnsembleResult) -> str:
    """Generate a 2-3 paragraph human-readable explanation."""
    explanations = []
    
    # Add explanation for each significant signal
    if result.engine_component > 0.2:
        explanations.append(format_template("engine_agreement_high", signals))
    if result.timing_component > 0.15:
        explanations.append(format_template("timing_anomaly", signals))
    if result.streak_component > 0.15:
        explanations.append(format_template("streak_improbability", signals))
    if signals.sniper_gap > 0.25:
        explanations.append(format_template("critical_accuracy_spike", signals))
    
    # Combine into coherent narrative
    intro = f"ChessGuard has identified {signals.player} as {result.risk_level} risk " \
            f"with {result.confidence:.0%} confidence based on the following evidence:"
    
    return intro + "\n\n" + "\n\n".join(explanations[:3])  # Top 3 reasons
```

---

## 7. API Endpoints

### 7.1 Account Management

```
POST   /api/accounts/connect/lichess     # Initiate Lichess OAuth
POST   /api/accounts/connect/chesscom    # Initiate Chess.com OAuth
GET    /api/accounts                     # List connected accounts
DELETE /api/accounts/{id}                # Disconnect account
PATCH  /api/accounts/{id}/sync           # Enable/disable sync
```

### 7.2 Agent Control

```
GET    /api/agent/status                 # Current agent state & next run
POST   /api/agent/sync/now               # Trigger immediate sync
GET    /api/agent/jobs                   # List past sync jobs
GET    /api/agent/jobs/{id}              # Job detail with stats
```

### 7.3 Reports

```
GET    /api/reports                      # List all generated reports
GET    /api/reports/{id}                 # Report detail (JSON)
GET    /api/reports/{id}/pdf             # Download PDF
GET    /api/reports/flagged              # All flagged players with summaries
POST   /api/reports/{id}/dismiss         # Mark false positive
```

---

## 8. User Interface Additions

### 8.1 Account Connection Screen

```
┌─────────────────────────────────────────────────────────────┐
│  🔗 Connected Accounts                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Lichess    [DrNykterstein]    Last sync: 2h ago   [Disconnect]
│  ☑ Auto-sync daily                                          │
│                                                             │
│  Chess.com  [Not Connected]    [Connect Account →]          │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  📊 Sync Statistics                                          │
│  • 1,247 games analyzed this month                           │
│  • 23 unique opponents checked                               │
│  • 2 players flagged                                         │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Dashboard Flagged Players Panel

```
┌─────────────────────────────────────────────────────────────┐
│  🚩 Flagged Opponents                           [View All →] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔴 SuspiciousUser123 (Chess.com)          Score: 0.91      │
│     "94% engine match in critical positions"                 │
│     3 games • Flagged 12h ago              [View Report →]  │
│                                                             │
│  🟠 WeirdTimer99 (Lichess)                  Score: 0.76      │
│     "Timing patterns inconsistent with rating"              │
│     7 games • Flagged 2d ago               [View Report →]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 Report Viewer

- Interactive chart showing ensemble score breakdown
- Game timeline with suspicious games highlighted
- Embedded chess board replaying flagged moves
- Export buttons (PDF, JSON, Copy Link)

---

## 9. Security & Privacy

| Concern | Mitigation |
|---------|------------|
| **Token Storage** | AES-256 encryption at rest; tokens never logged |
| **Scope Minimization** | Request only `game:read` access; no write permissions |
| **Data Retention** | Game data purged after 90 days unless user opts in |
| **Report Access** | Reports visible only to generating user; no public sharing by default |
| **Rate Limits** | User-level throttling prevents abuse |
| **Audit Logging** | All agent actions logged with timestamps |

---

## 10. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **API Changes** | Sync breaks | Medium | Version-specific adapters; monitor changelogs |
| **False Positives** | User trust loss | Medium | Conservative thresholds; "Dismiss" feedback loop |
| **Rate Limiting** | Slow syncs | High | Smart batching; user-configurable timing |
| **OAuth Revocation** | Silent failure | Medium | Token health checks; user notification |
| **Report Misuse** | Harassment | Low | No public sharing; watermarked PDFs |

---

## 11. Dependencies

| Dependency | Purpose | Status |
|------------|---------|--------|
| Existing `GameAnalysisPipeline` | Core analysis | ✅ Ready |
| Existing `ensemble_score.py` | Scoring | ✅ Ready |
| Existing `reporting.py` | PDF generation | ✅ Ready |
| Lichess OAuth | Account connection | ✅ Exists in `/api/lichess/` |
| Chess.com OAuth | Account connection | 🔶 Needs implementation |
| Celery/Redis OR APScheduler | Job scheduling | 🔶 Needs setup |
| Email service (SendGrid/SES) | Notifications | 🔶 Needs integration |

---

## 12. Out of Scope (V1)

- Real-time game monitoring (live games)
- Mobile push notifications
- Multi-language report generation
- Direct platform reporting integration (auto-file reports)
- Browser extension integration
- Public leaderboard of flagged cheaters

---

## 13. Roadmap

### Phase 1: Foundation (2 weeks)
- [ ] Implement `connected_accounts` model and OAuth flows
- [ ] Build `game_sync_agent.py` with Lichess support
- [ ] Create basic job tracking and status API

### Phase 2: Analysis Integration (2 weeks)
- [ ] Implement `opponent_aggregator.py` to group games by opponent
- [ ] Extend ensemble scoring for multi-game opponent analysis
- [ ] Build `explanation_engine.py` with template system

### Phase 3: Reporting (1 week)
- [ ] Extend `EvidenceReport` with explanation sections
- [ ] Build email digest templates
- [ ] Create report listing and export API endpoints

### Phase 4: UI & Polish (1 week)
- [ ] Account connection UI
- [ ] Dashboard flagged players panel
- [ ] Report viewer with embedded board

### Phase 5: Chess.com Integration (1 week)
- [ ] Implement Chess.com OAuth (or API key flow)
- [ ] Adapt game fetcher for Chess.com API format
- [ ] Unified opponent view across platforms

---

## 14. Open Questions

1. **Chess.com OAuth**: Does Chess.com support OAuth 2.0, or should we use public API + user-provided username?
2. **Analysis Depth**: Should agent use faster analysis (depth 12) for volume, or full depth 16?
3. **Notification Frequency**: Daily digest vs. immediate alerts for CRITICAL flags?
4. **Historical Limit**: How far back should initial sync analyze (30/60/90 days)?
5. **Free vs. Paid**: Should agent features be gated behind a subscription?

---

## 15. Appendix: Existing Services Reference

### Key Files to Extend

| File | Current Purpose | Extension Needed |
|------|-----------------|------------------|
| `server/services/analysis.py` | Single-game analysis | Add batch mode |
| `server/services/ensemble_score.py` | Game-level scoring | Add player-level aggregation |
| `server/services/reporting.py` | Basic PDF | Add explanation sections |
| `server/services/lichess.py` | OAuth + game fetch | Add incremental sync tracking |
| `server/api/lichess_audit.py` | Manual audit trigger | Basis for auto-audit |

### Detection Signals Already Available

From `DetectionSignals` dataclass:
- `engine_agreement` / `adjusted_engine_agreement`
- `timing_suspicion` / `scramble_toggle_score`
- `streak_improbability` / `critical_position_accuracy`
- `complexity_correlation` / `sniper_gap`
- `opponent_correlation_score` / `session_fatigue_score`

All 15 signals can be aggregated across multiple games for opponent-level analysis.

---

## 16. Cheater Training Data Warehouse

### 16.1 Purpose

A centralized data warehouse of **verified cheater games** to train and continuously improve ChessGuard's ML detection models. The warehouse aggregates data from multiple sources, normalizes it into a unified schema, and provides labeled training datasets for supervised learning.

### 16.2 External Data Sources

| Source | Type | Volume | Access Method | Notes |
|--------|------|--------|---------------|-------|
| **Kaggle Cheating Dataset** | Synthetic | 48K games | Direct download | Bot vs bot with one side using Stockfish/Maia; labeled `cheater` flag |
| **Lichess Database** | Real games | 5B+ games | `database.lichess.org` | Filter by accounts with "fair play violation" status via API |
| **Lichess Closed Accounts** | Banned users | ~100K/month | `lichess.org/api/user/{id}` | Check `disabled` + `tosViolation` flags |
| **Chess.com Archived Cheaters** | Historical | ~50K accounts | Archive.org + API | "Cheating is For Losers" archive; verify via `/pub/player/{id}` status |
| **FICS Games Archive** | Research | Millions | `ficsgames.org` | Academic dataset for ML research |
| **Maia Cheater-Style Corpus** | Synthetic | Variable | Open source | Human-like but engine-assisted move patterns |
| **ChessGuard Discovered** | Crawled | Growing | Internal | From `discover_cheaters.py` BFS crawler |

### 16.3 Ingestion Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DATA WAREHOUSE PIPELINE                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐  │
│  │   Kaggle    │   │  Lichess    │   │ Chess.com   │   │  ChessGuard     │  │
│  │   Dataset   │   │  Database   │   │   Archive   │   │    Crawler      │  │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └───────┬─────────┘  │
│         │                 │                 │                   │            │
│         ▼                 ▼                 ▼                   ▼            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     SOURCE ADAPTERS (per-source ETL)                  │   │
│  │  • kaggle_adapter.py  • lichess_adapter.py  • chesscom_adapter.py    │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                           │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       NORMALIZATION LAYER                             │   │
│  │  • PGN parsing & validation   • Unified schema mapping               │   │
│  │  • Rating normalization       • Time control classification          │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                           │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    FEATURE EXTRACTION ENGINE                          │   │
│  │  • Engine analysis (Stockfish depth 16)  • Timing pattern extraction │   │
│  │  • Accuracy metrics calculation          • Complexity scoring        │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                           │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     TRAINING DATA WAREHOUSE                           │   │
│  │              PostgreSQL + Parquet files for ML pipelines              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 16.4 Unified Data Schema

```sql
-- Core game table with cheater labels
CREATE TABLE training_games (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,          -- 'kaggle' | 'lichess' | 'chesscom' | 'crawled'
    source_game_id VARCHAR(100),          -- Original ID from source
    pgn TEXT NOT NULL,
    
    -- Player information
    white_username VARCHAR(100),
    black_username VARCHAR(100),
    white_rating INTEGER,
    black_rating INTEGER,
    
    -- Labels (ground truth)
    cheater_side VARCHAR(10),             -- 'white' | 'black' | 'both' | 'none'
    cheater_type VARCHAR(50),             -- 'engine_full' | 'engine_selective' | 'unknown'
    ban_confirmed BOOLEAN DEFAULT false,  -- Verified by platform
    ban_date TIMESTAMP,
    
    -- Time control
    time_control VARCHAR(50),
    time_class VARCHAR(20),               -- 'bullet' | 'blitz' | 'rapid' | 'classical'
    
    -- Extracted features (pre-computed for ML)
    features JSONB,                       -- All 15 detection signals
    
    -- Metadata
    game_date TIMESTAMP,
    ingested_at TIMESTAMP DEFAULT NOW(),
    analyzed BOOLEAN DEFAULT false
);

-- Pre-computed feature vectors for ML training
CREATE TABLE training_features (
    game_id INTEGER REFERENCES training_games(id),
    
    -- Core signals (normalized 0-1)
    engine_agreement FLOAT,
    adjusted_engine_agreement FLOAT,
    timing_suspicion FLOAT,
    scramble_toggle_score FLOAT,
    streak_improbability FLOAT,
    critical_position_accuracy FLOAT,
    complexity_correlation FLOAT,
    sniper_gap FLOAT,
    opponent_correlation_score FLOAT,
    session_fatigue_score FLOAT,
    
    -- Additional ML features
    avg_centipawn_loss FLOAT,
    move_time_variance FLOAT,
    critical_moves_correct_pct FLOAT,
    book_exit_accuracy FLOAT,
    
    -- Label
    is_cheater BOOLEAN NOT NULL,
    
    PRIMARY KEY (game_id)
);

-- Index for efficient filtering
CREATE INDEX idx_training_games_source ON training_games(source);
CREATE INDEX idx_training_games_cheater ON training_games(cheater_side);
CREATE INDEX idx_training_features_label ON training_features(is_cheater);
```

### 16.5 Source Adapters

Each data source requires a dedicated adapter to fetch and normalize data:

```python
# data_warehouse/adapters/base.py
class BaseAdapter(ABC):
    @abstractmethod
    async def fetch_games(self, limit: int = 1000) -> List[RawGame]:
        """Fetch raw games from source."""
        pass
    
    @abstractmethod
    def normalize(self, raw: RawGame) -> TrainingGame:
        """Convert source-specific format to unified schema."""
        pass
    
    @abstractmethod
    def get_cheater_label(self, raw: RawGame) -> CheaterLabel:
        """Determine ground truth label for the game."""
        pass
```

**Kaggle Adapter** (simplest - pre-labeled):
```python
class KaggleAdapter(BaseAdapter):
    def get_cheater_label(self, raw: RawGame) -> CheaterLabel:
        # Kaggle dataset has explicit 'cheater' column
        return CheaterLabel(
            side=raw['cheater'],  # 'white' or 'black'
            type='engine_full',
            confirmed=True
        )
```

**Lichess Adapter** (API-based discovery):
```python
class LichessAdapter(BaseAdapter):
    async def discover_cheaters(self) -> List[str]:
        """BFS crawl to find closed accounts."""
        # Similar to existing discover_cheaters.py
        # Check user status for 'tosViolation'
        pass
    
    async def fetch_games(self, username: str) -> List[RawGame]:
        # Use database.lichess.org or API
        pass
```

### 16.6 Data Collection Schedule

| Source | Frequency | Method | Volume/Run |
|--------|-----------|--------|------------|
| Kaggle | One-time | Download | 48K games |
| Lichess Crawler | Weekly | BFS + API | ~500 new cheaters |
| Chess.com Archive | Monthly | Scrape + verify | ~1K accounts |
| ChessGuard Reports | Continuous | User feedback | Variable |

### 16.7 ML Training Integration

The data warehouse provides training data in formats suitable for different ML frameworks:

```python
# data_warehouse/exports/training_export.py

def export_for_sklearn(split: float = 0.8) -> Tuple[np.ndarray, np.ndarray]:
    """Export feature vectors and labels for scikit-learn."""
    df = pd.read_sql("SELECT * FROM training_features", conn)
    X = df.drop(columns=['game_id', 'is_cheater']).values
    y = df['is_cheater'].astype(int).values
    return train_test_split(X, y, train_size=split)

def export_for_pytorch() -> torch.utils.data.Dataset:
    """Export as PyTorch Dataset for neural networks."""
    return ChessCheatDataset(db_conn)

def export_parquet(path: str):
    """Export to Parquet for distributed training (Spark, Dask)."""
    df.to_parquet(path, engine='pyarrow')
```

### 16.8 Training Pipeline

```python
# ml/train_detector.py

class CheatDetectorTrainer:
    def __init__(self, warehouse: DataWarehouse):
        self.warehouse = warehouse
        
    def train_ensemble(self):
        """Train the main ensemble classifier."""
        X_train, X_test, y_train, y_test = self.warehouse.export_for_sklearn()
        
        # Gradient Boosting (primary)
        gb_model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1
        )
        gb_model.fit(X_train, y_train)
        
        # Random Forest (secondary)
        rf_model = RandomForestClassifier(n_estimators=100)
        rf_model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = gb_model.predict(X_test)
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")
        print(f"Precision: {precision_score(y_test, y_pred):.3f}")
        print(f"Recall: {recall_score(y_test, y_pred):.3f}")
        
        return gb_model, rf_model
```

### 16.9 Data Quality & Validation

| Check | Method | Threshold |
|-------|--------|-----------|
| **Label Accuracy** | Cross-validate with platform bans | 95%+ match rate |
| **Feature Completeness** | NULL check on required columns | <1% missing |
| **Duplicate Detection** | Hash PGN + player IDs | 0 duplicates |
| **Rating Sanity** | Range check (0-3500) | No outliers |
| **Time Control Balance** | Distribution analysis | No >80% single TC |

### 16.10 Privacy & Ethics

- **No Personal Data**: Store only usernames (public) and game data
- **Right to Deletion**: Remove games if user requests via platform
- **Research Only**: Training data not exposed externally
- **Anonymization Option**: Hash usernames for public datasets
- **Bias Monitoring**: Track detection rates by rating bracket, time control

### 16.11 New Files to Create

```
data_warehouse/
├── __init__.py
├── adapters/
│   ├── __init__.py
│   ├── base.py              # Base adapter interface
│   ├── kaggle_adapter.py    # Kaggle dataset ingestion
│   ├── lichess_adapter.py   # Lichess API + database
│   └── chesscom_adapter.py  # Chess.com archive + API
├── pipeline/
│   ├── __init__.py
│   ├── normalizer.py        # Unified schema conversion
│   ├── feature_extractor.py # Signal extraction for ML
│   └── scheduler.py         # Cron-based ingestion jobs
├── exports/
│   ├── __init__.py
│   ├── sklearn_export.py    # numpy array export
│   ├── pytorch_export.py    # PyTorch Dataset
│   └── parquet_export.py    # Parquet for Spark
└── models/
    └── schema.py            # SQLAlchemy models

ml/
├── __init__.py
├── train_detector.py        # Model training script
├── evaluate.py              # Model evaluation
└── models/
    ├── gradient_boost.pkl   # Trained GB model
    └── random_forest.pkl    # Trained RF model
```

### 16.12 Roadmap for Data Warehouse

| Phase | Tasks | Timeline |
|-------|-------|----------|
| **Phase 1** | Ingest Kaggle dataset; create base schema | Week 1 |
| **Phase 2** | Lichess adapter + BFS crawler integration | Week 2 |
| **Phase 3** | Feature extraction pipeline | Week 3 |
| **Phase 4** | ML training integration + baseline model | Week 4 |
| **Phase 5** | Chess.com adapter + continuous ingestion | Week 5-6 |
