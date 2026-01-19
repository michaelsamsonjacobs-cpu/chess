# ChessGuard Data Directory

This folder holds all datasets used by the ChessGuard project.  The sub-folders
mirror the lifecycle of a record as it flows from ingestion through model
training.  Unless otherwise stated, all paths referenced by the codebase are
relative to this directory.

## Storage Layout

- `raw/` – Immutable snapshots as delivered by external providers.  Files in
  this directory are stored exactly as received (including compression).  Each
  file name should encode the source, acquisition date, and checksum so that the
  provenance of every row can be reconstructed.
- `interim/` – Temporary, workshop-style assets produced while cleaning and
  validating raw data.  Examples include partially parsed PGN files, schema
  validation reports, or deduplicated subsets waiting for analyst sign-off.
- `processed/` – Canonical tables ready for downstream analytics and model
  training.  These are typically stored as Parquet or Arrow files produced by
  the ingestion pipelines in `chessguard/data/`.
- `artifacts/` – Optional location for feature matrices, trained model weights,
  and evaluation reports emitted by `chessguard/training/train.py`.

## Retention Rules

- **Raw data** is retained for 180 days to facilitate audits and reproducibility.
  After that period the files must either be archived to offline storage or
  deleted if a newer, verified snapshot is available.
- **Interim data** is ephemeral and should be purged automatically after 30 days
  or once a processed equivalent has been generated, whichever happens first.
- **Processed data** is kept until it is superseded by a newer release.  At that
  point the previous version may be archived but should remain accessible for at
  least one full training cycle.
- **Artifacts** should follow the model governance policy documented in
  `docs/data_governance.md`.  Production-critical models must retain their
  training datasets, configuration files, and evaluation logs for one year.

All directories are intentionally empty in version control; pipelines are
responsible for creating dated sub-folders as needed.
