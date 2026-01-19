# Testing Guide

The goal of this document is to make it easy to validate ChessGuard locally
and provide a repeatable outline for future automated suites. Even though the
core application is still under heavy development, the lightweight mock server
in `scripts/dev_server.py` and the seed data in `seeds/` let you exercise the
baseline assumptions quickly.

## Prerequisites

Before testing, complete the setup steps described in the [README](../README.md):

- Install Python 3.11 or newer.
- Create and activate a virtual environment.
- Install project dependencies with `pip install -r requirements.txt` (the file
  is currently a placeholder until runtime packages are defined).
- Copy `.env.example` to `.env`, adjust values, and export them in your shell.

## Seed Data Reference

Two JSON fixtures ship with the repository and are used by the mock
implementation:

| File | Purpose | Notes |
| --- | --- | --- |
| `seeds/sample_players.json` | Master list of notable players | Fields include `id`, `name`, `federation`, `title`, and `rating`. |
| `seeds/sample_games.json` | Minimal historic games for smoke tests | Fields include `id`, `white_player_id`, `black_player_id`, `result`, `event`, `moves`, and `played_at`. |

If you expand the dataset or add new fixtures, prefer JSON for quick iteration
and document the schema in this table.

## Manual Test Plan

### 1. Environment sanity check

1. Copy the `.env.example` file to `.env` and adjust secrets if necessary.
2. Export variables into your shell: `set -a && source .env && set +a`.
3. Start the placeholder dev server in a dedicated terminal:
   ```bash
   python scripts/dev_server.py
   ```
4. The console should display the URL it is listening on; the default is
   `http://localhost:8000`.

### 2. API smoke tests

Use `curl`, HTTPie, or a browser to exercise the mock endpoints while the server
is running.

- Health check:
  ```bash
  curl http://localhost:8000/health
  ```
  Expect a JSON response containing `{"status": "ok"}` and the active
  environment.
- Fetch players:
  ```bash
  curl http://localhost:8000/players | jq
  ```
  Confirm the response contains three records and that the schema matches
  `seeds/sample_players.json`.
- Fetch games:
  ```bash
  curl http://localhost:8000/games | jq
  ```
  Ensure the response includes the two sample games and references valid
  `player_id` values.
- Negative route handling:
  ```bash
  curl -i http://localhost:8000/unknown
  ```
  Verify the server returns a `404` and a JSON body describing the supported
  routes.

### 3. Data integrity cross-checks

- Compare player IDs in `sample_games.json` with the `players` dataset; every
  game should reference existing players.
- Validate the timestamps in `sample_games.json` are formatted using ISO-8601 to
  ensure downstream consumers can parse them.
- Confirm each player entry contains a `rating` integer so analytics code can
  compute aggregates.

### 4. Logging and observability

- Set `LOG_LEVEL=DEBUG` in your `.env` and restart the server. Repeat the smoke
  tests and confirm request logs now appear in the console.

## Automated Test Strategy

Automated suites do not ship with the repository yet, but the following plan
should be followed once the implementation lands:

- **Unit tests** – Cover pure functions and request handlers using `pytest`.
  Adopt a structure such as `tests/unit/` and run them via
  `pytest tests/unit`.
- **Integration tests** – Spin up the dev server in-process (for example using
  `pytest` fixtures) and assert responses against the seed data. Store them in
  `tests/integration/` and execute `pytest tests/integration`.
- **End-to-end (E2E) tests** – When a UI exists, exercise the whole stack with a
  browser automation framework such as Playwright or Cypress. These tests should
  rely on the JSON fixtures to guarantee deterministic state.

Once CI pipelines are introduced, ensure they run the three stages in the above
order so failures surface early.

## Data Input Expectations

When building new features, keep the following conventions in mind so your code
remains compatible with the published fixtures and manual checks:

- **Identifiers** – Use stable string IDs prefixed with the entity type
  (`player-`, `game-`, etc.) to simplify debugging.
- **Ratings** – Store ratings as integers in Elo points. Automated validation
  should reject negative values.
- **Timestamps** – Record times in UTC using ISO-8601 with the `Z` suffix.
- **Move lists** – Represent chess moves as SAN (Standard Algebraic Notation)
  strings ordered by ply.

These constraints should be encoded into model validation once the actual
service layer is added.
