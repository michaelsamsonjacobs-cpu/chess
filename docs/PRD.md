# ChessGuard Product Requirements Document

## 1. Overview
ChessGuard is a statistical cheat-detection platform that helps federations, online platforms, and professional players evaluate suspicious performance patterns. The product combines streak-based anomaly detection, engine-correlation checks, and behavior audits into an auditable workflow. This revision incorporates a replication pipeline that stress-tests the Rosenthal (HDSR 2025) streak methodology and expands ingestion so that analysts can evaluate **entire series of games** in aggregate.

## 2. Objectives & Success Metrics
- **Trustworthy analytics:** Deliver reproducible streak probabilities and supporting artifacts for every flagged run.
- **Broad ingest coverage:** Support direct pulls or bulk uploads of complete playing histories (e.g., tournaments, rolling 2,000 game windows) from Chess.com, Lichess, and federation databases.
- **Operational readiness:** Provide turn-key reports within 5 minutes for 95% of batch analyses up to 2,500 games.
- **Adoption:** Secure three pilot integrations (two platforms, one federation) with recurring use of batch streak reviews by Q4.

## 3. Target Users & Use Cases
- **Integrity analysts:** Need to ingest a suspect player’s entire blitz history, replay detection pipelines, and export documented evidence.
- **Tournament directors:** Require tournament-level uploads (PGN, JSON exports) to audit round-by-round results for entire sections.
- **Professional players & teams:** Want rapid self-checks on their own archives to preempt accusations.
- **Platform trust & safety teams:** Automate rolling window monitoring for all top-tier accounts using APIs.

## 4. Functional Requirements
### 4.1 Multi-Game Collection & Upload
- Provide UI and API endpoints for uploading zipped PGNs, JSON archives, or CSV summaries containing **entire series of games**.
- Enable direct pulls via OAuth tokens from Chess.com and Lichess for predefined users or cohorts; support scheduling recurring synchronizations for rolling histories.
- Maintain metadata describing source, time control, rating system, disconnects, or bot-tagged games for downstream filters.
- Validate completeness (no missing rounds, overlapping games) and log discrepancies with explicit reasons (e.g., disconnect, abort, overlap) before analysis.

### 4.2 Batch Analysis Orchestration
- Queue full-series jobs so analysts can run streak probabilities, engine-alignment, and behavior heuristics as a cohesive bundle.
- Allow analysts to select peer cohorts (default top-20 blitz players; optional custom sets) and configure rolling windows (e.g., last 2,000 games).
- Store normalized game sets so users can re-run analyses under alternative definitions without re-uploading data.

### 4.3 Results & Reporting
- Produce downloadable streak summaries (`streak_summary.json`), peer comparison tables (`subject_probs.csv`), and annotated discrepancy logs for transparency.
- Visualize streak likelihoods, peer baselines (7-player vs 20-player cohorts), and highlight overlaps with engine-detection outcomes inside dashboards and PDF briefs.
- Flag critical alerts when streak probabilities fall below configurable thresholds or when multiple detection subsystems agree.

## 5. System Architecture & Data Pipeline
- **Ingestion service:** Handles bulk uploads, API pulls, schema validation, and metadata tagging for series-level datasets.
- **Processing engine:** Normalizes games, enriches with platform ratings, and streams batches to detection workers.
- **Detection workers:** Run streak analytics (Rosenthal replication + robustness tests), engine correlation, and behavioral heuristics in parallel.
- **Artifact store:** Persists intermediate outputs (probability tables, logs) for audit replay and third-party review.
- **Access layer:** Web portal and REST API for submitting jobs, monitoring progress, and downloading reports.

## 6. Technical Validation & Replication Strategy
To bolster confidence in streak-based accusations, ChessGuard ships a transparent replication toolkit:
- **Open replication scripts:** `chess_streak_replication.py`, `streak_analyzer.py`, and a Colab notebook let stakeholders re-run analyses directly on Chess.com exports.
- **Expanded peer cohorts:** Default comparisons span the top-20 blitz players (vs. the original 7-player subset) to remove selection-bias critiques; analysts can pivot to custom cohorts.
- **Consistent rating calibration:** Fit logistic win/draw/loss probabilities on native Chess.com ratings, avoiding Elo vs. Glicko mismatches.
- **Calendar-aware streaks:** Compute streak probabilities in actual game order, supporting overlapping and rolling windows that mirror live-monitoring conditions.
- **Transparent artifacts:** Expose auditable outputs (`subject_probs.csv`, `streak_summary.json`) and discrepancy explanations (disconnects, overlaps, bot games).
- **Live reruns:** The engine can execute these scripts on freshly ingested accounts in near real time, not just on archived datasets.

## 7. Robustness Analysis & Reporting Enhancements
- Include a dedicated "Robustness Analysis" section in dashboards and stakeholder decks comparing streak probabilities under multiple peer cohorts (7-player baseline vs. 20-player default) and definition variants.
- Provide toggles for alternative time controls (bullet, rapid) leveraging the same pipeline with minimal configuration changes.
- Surface sensitivity studies showing how probability estimates shift with peer selection, streak lengths, or exclusion rules.
- Reference cutting-edge algorithms (e.g., Diao 2025) to emphasize the methodological roadmap and align with anticipated peer-reviewed validations.

## 8. Security, Compliance & Auditability
- Enforce role-based access for ingestion endpoints; sensitive uploads stored encrypted at rest.
- Maintain full audit logs linking each report to the input dataset, code version, and configuration used.
- Publish replication instructions so external investigators can verify ChessGuard’s conclusions.

## 9. Roadmap & Next Steps
1. Implement unified batch-ingestion APIs and UI flows for full-series uploads and scheduled pulls.
2. Integrate replication outputs and discrepancy logs into the Technical Validation dashboard section.
3. Build the Robustness Analysis module with cohort comparison charts and export templates.
4. Pilot live streak reruns on target accounts with partner platforms, capturing run-time metrics.
5. Extend analytics to bullet and rapid datasets using the existing replication pipeline foundation.
