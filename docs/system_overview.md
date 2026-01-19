# ChessGuard System Overview

ChessGuard operationalises lessons from community cheating-detection projects into a modular pipeline suitable for production use. The system is divided into three layers: data ingestion, engine-assisted analysis, and decision support.

## 1. Data Ingestion Layer

| Component | Responsibilities | Key Insights Applied |
| --- | --- | --- |
| **Lichess connector** | Streams recent games via the `/api/games/user` endpoint (NDJSON) with metadata such as clocks, ratings, and accuracy. | Borrowed batching and persistence patterns from `Avar111ce/Detecting-cheaters-on-lichess` to enable statistical baselines. |
| **Chess.com connector** | Downloads monthly archives (`/pub/player/{user}/games/{yyyy}/{mm}`) and merges them with tournament metadata. | Follows `RubenLazell/Detecting-Cheating-in-Online-Chess` by keeping large archives on disk for retrospective studies. |
| **Event sampler** | Focused fetcher for rapid events (e.g., Chess.com Titled Tuesday) with per-move time tracking. | Inspired by `bhajji56/cheating-analysis`, emphasising quick-move scenarios. |

## 2. Engine-Assisted Analysis

| Module | Responsibilities | Key Metrics |
| --- | --- | --- |
| **Move evaluation** | Uses Stockfish (configurable depth/time) to evaluate each ply, retrieving best moves and centipawn scores. | Centipawn loss per move, blunder/mistake/accuracy labels (`Avar111ce` baseline). |
| **Time-pressure heuristics** | Correlates time spent with engine agreement rate. | Identifies high-accuracy sequences completed in <10 seconds (`bhajji56`). |
| **Contextual baselines** | Normalises metrics against player rating, time control, and opening complexity. | Recreates distributions observed in `cbarger233` EDA notebooks. |

## 3. Decision Support

| Asset | Purpose |
| --- | --- |
| **Suspicion score** | Weighted aggregation of centipawn-loss anomalies, engine agreement streaks, and time-pressure red flags. |
| **Case study notebooks** | Rich, reproducible narratives combining charts, annotated PGNs, and textual summaries for moderators. |
| **Dashboard (planned)** | Live surface to monitor flagged accounts, compare to baselines, and inspect move-level evidence. |

## Data Flow

1. **Acquire games** from APIs or curated archives.
2. **Store raw data** as NDJSON/PGN files plus metadata tables (CSV/Parquet).
3. **Enrich** each move with Stockfish evaluations and time deltas.
4. **Aggregate metrics** per game, event, and player session.
5. **Score** the aggregated metrics against configurable thresholds.
6. **Publish** results to notebooks, dashboards, or moderation queues.

## Extensibility Hooks

- **Engine adapters** – wrap additional UCI engines or remote evaluation services.
- **Feature registry** – plug in new features (e.g., move-matching sequences, novelty detection) without rewriting the pipeline.
- **Model experimentation** – integrate classical statistics or machine-learning classifiers on top of the curated feature tables.

## Next Steps

- Implement a persistent metadata store (DuckDB or SQLite) to enable rapid slicing by player, event, and rating.
- Automate scheduled fetches for active tournaments to build rolling baselines.
- Publish a public schema for moderated case files so external researchers can contribute audits.
