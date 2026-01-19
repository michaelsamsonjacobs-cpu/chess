# ChessGuard Architecture

ChessGuard separates data acquisition, feature engineering, modelling and
reporting into explicit modules.  The diagram below illustrates the flow:

```
PGN / Telemetry -> data.loader -> FeatureVector -> models -> DetectionReport
```

## Components

### Data Layer

* `chessguard.utils.pgn` – dependency-free PGN parser producing `PGNGame`
  structures.
* `chessguard.data.loader` – utilities for reading PGN files and telemetry
  feeds (JSON/CSV) into structured Python objects.
* `chessguard.data.telemetry` – data classes for move timing with helper
  statistics.

### Feature Engineering

* `chessguard.features.extractor` – orchestrates move- and timing-based
  features, merges them into a `FeatureVector` and computes derived balances.
* `chessguard.features.timing` – summarises pacing metrics such as burstiness
  and tempo shifts.

### Modelling

* `chessguard.models.baseline.RuleBasedModel` – interpretable heuristics with
  explicit textual rationales.
* `chessguard.models.hybrid.HybridLogisticModel` – logistic regression with
  optional gradient descent fitting and contribution tracing.
* `chessguard.models.base` – shared interfaces used by all detectors.

### Pipeline & Reporting

* `chessguard.pipeline.detection.DetectionPipeline` – coordinates feature
  extraction, invokes each configured model and aggregates the scores.
* `chessguard.reporting.explain` – turns structured reports into textual
  summaries for arbiters and analysts.

### Command Line Interface

Running `python -m chessguard` leverages the CLI defined in
`chessguard.cli`, which loads the requested files, executes the pipeline and
prints both the textual and JSON (optional) representations.

## Extending the Stack

1. **New Features** – create additional extractor functions and merge the
   results into the `FeatureVector`.
2. **Custom Models** – implement `DetectionModel.predict` and pass new
   instances to `DetectionPipeline(models=[...])`.
3. **Alternative Outputs** – use `DetectionReport.to_dict()` to build web UIs
   or persist structured audit logs.

## Testing Strategy

* Unit tests validate PGN parsing, feature coverage and pipeline behaviour.
* Sample assets under `examples/` provide reproducible fixtures.
* Continuous integration should run `python -m pytest` on every change.

## Future Enhancements

* Expand PGN parsing to support comments, alternate lines and NAG codes.
* Integrate calibration datasets to translate scores into probabilities.
* Support incremental telemetry streaming for live monitoring contexts.
