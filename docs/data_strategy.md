# Data Strategy

ChessGuard synthesises the data-handling strategies from the surveyed community
repositories into a cohesive plan that supports both experimentation and
operations.

## Source Coverage

- **Lichess** – incremental pulls via `/api/games/user` and `/api/games/tournament`
  endpoints. Raw NDJSON payloads are stored for reproducibility, while curated
  feature tables mirror `Avar111ce/Detecting-cheaters-on-lichess`'s CSV exports.
- **Chess.com** – monthly archives for breadth plus event-focused samplers for
  high-stakes tournaments (e.g., Titled Tuesday) in line with
  `bhajji56/cheating-analysis` and `RubenLazell/Detecting-Cheating-in-Online-Chess`.
- **Community flags** – support ingesting moderator reports and user-submitted
  suspicions to drive prioritised analyses and case studies.

## Storage Layout

| Layer | Format | Purpose |
| --- | --- | --- |
| Raw | NDJSON / PGN | Exact API responses for auditability. |
| Staging | Parquet | Normalised move-level tables with evaluation metadata. |
| Derived | DuckDB / SQLite | Aggregated summaries for dashboards and ad-hoc SQL. |

## Feature Synchronisation

- Engine evaluations are cached per move to avoid recomputation and to match the
  reproducibility goals seen in academic theses such as
  `RubenLazell/Detecting-Cheating-in-Online-Chess`.
- Time-to-move statistics and engine agreement flags are computed in tandem so
  that case studies can highlight fast, engine-like decisions as in
  `bhajji56/cheating-analysis`.

## Governance

- Maintain metadata for engine version, depth/time settings, and dataset hashes
  to ensure like-for-like comparisons across studies.
- Document known biases (rating distributions, time controls) to contextualise
  results when sharing with moderators or the wider community.
