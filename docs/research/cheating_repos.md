# Community Repositories Survey

This document distils the most actionable ideas from four open-source projects that document or analyse chess engine-assisted cheating. These references shape ChessGuard's roadmap and provide validation data for our experiments.

## Avar111ce/Detecting-cheaters-on-lichess

- **Data acquisition** – demonstrates how to query the Lichess API for historical games and tournament snapshots, persisting the results as CSVs (`players_stats.csv`, `tournament_stats.csv`).
- **Engine benchmarking** – runs Stockfish locally to compute centipawn-loss metrics that separate honest from suspicious play.
- **Feature engineering** – highlights mistake counts, accuracy, and rating deltas as key signals.
- **Takeaway for ChessGuard** – reuse the API query structure and replicate their statistical baselines when validating new features.

## cbarger233/Chess-Game-Analysis

- **Exploratory notebooks** – Kaggle-derived Lichess game dump drives a full exploratory data analysis (EDA) workflow.
- **Case study workflow** – pairs Stockfish evaluations with manual annotations to surface engine-like sequences in user-submitted complaints.
- **Takeaway for ChessGuard** – emphasises reproducible notebooks and visual storytelling for moderators; adopt similar notebook templates.

## bhajji56/cheating-analysis

- **Chess.com Titled Tuesday focus** – curates under-ten-second critical moves from elite rapid events, enabling a time-pressure lens on cheating.
- **Batch Stockfish analysis** – scripts compare the human move with engine best moves, producing per-move agreement flags.
- **Takeaway for ChessGuard** – integrate time-to-move and complexity-aware heuristics into the scoring model to catch rapid decision anomalies.

## RubenLazell/Detecting-Cheating-in-Online-Chess

- **Large-scale dataset** – multi-gigabyte PGN archive spanning several high-profile tournaments on Chess.com.
- **Research documentation** – includes methodology write-ups detailing statistical thresholds, which offer baseline expectations for model calibration.
- **Takeaway for ChessGuard** – treat the repository as a benchmark corpus for cross-validation and stress testing of detection heuristics.

## Implementation Implications

- Maintain connectors for both Lichess (REST/NDJSON) and Chess.com (monthly archives) so new studies can be replicated quickly.
- Normalise centipawn-loss, mistake, and accuracy metrics to rating bands before comparing players.
- Track time-to-move distributions and pair them with engine agreement to flag suspicious high-accuracy, low-time decisions.
- Provide notebook templates for case studies that combine statistical summaries with annotated critical moves.
