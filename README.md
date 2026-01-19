# ChessGuard

ChessGuard is a lightweight research toolkit for analysing chess games and telemetry to surface signals associated with engine-assisted play. It provides a modular pipeline that parses PGN files, engineers behavioural features, runs multiple detection models, and produces human-readable explanations. It also includes utilities for evaluating games with a UCI engine (e.g., Stockfish), curating datasets, and integrating with Lichess for ingestion/reporting.

---

## Project Goals

- **Reproducible pipeline** – deterministic feature extraction and model execution so experiments can be repeated and verified.
- **Explainable heuristics** – rule-based and statistical models return textual rationales for factors that influenced the risk score.
- **Telemetry aware** – move-timing feeds can be combined with PGN data to highlight engine-like pacing patterns.
- **Extensible architecture** – each stage (ingest, features, models, reporting) is encapsulated behind clear interfaces to encourage rapid experimentation.

---

## Repository Layout


