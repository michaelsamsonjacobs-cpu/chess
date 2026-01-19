# ChessGuard Observability Runbook

This runbook documents the alerting and dashboard strategy for the ChessGuard
pipeline. It is intended for the on-call engineer supporting the detection
service and evaluation harnesses.

## Metrics Overview

| Metric | Description | Notes |
| --- | --- | --- |
| `chessguard_engine_evaluations_total` | Counter of analysed games | Monotonic, exposed by the engine |
| `chessguard_engine_alerts_total` | Counter of games flagged for review | Should trend with tournaments |
| `chessguard_engine_latency_seconds` | Summary of per-game inference latency | Watch p95 | 
| `chessguard_engine_probability` | Histogram of emitted cheating probabilities | Used for calibration |
| `chessguard_service_requests_total` | Counter of API calls by endpoint | Primary SLO indicator |
| `chessguard_service_latency_seconds` | Summary of service latency | Track p95/p99 |
| `chessguard_service_inflight_requests` | Gauge of concurrent requests | Helps detect thundering herds |

All metrics are exported through Prometheus' default `/metrics` format via the
`ChessGuardService.export_metrics()` helper.

## Alert Thresholds

Alerts should be created on the following conditions:

1. **Service availability**
   - Trigger when `sum(rate(chessguard_service_requests_total{endpoint="evaluate_tournament"}[5m])) == 0`
     for 10 minutes during expected traffic windows. This indicates no requests
     are being processed.
   - Trigger a high severity alert when
     `histogram_quantile(0.95, rate(chessguard_service_latency_seconds_sum{endpoint="evaluate_tournament"}[5m]) / rate(chessguard_service_latency_seconds_count{endpoint="evaluate_tournament"}[5m])) > 1`
     second for 10 minutes.

2. **Engine health**
   - Page when `rate(chessguard_engine_alerts_total[15m]) / rate(chessguard_engine_evaluations_total[15m]) > 0.3`
     for two consecutive evaluation windows. A sudden spike in alerts usually
     indicates a bad model deploy or corrupted inputs.
   - Ticket when `rate(chessguard_engine_evaluations_total[1h]) < 0.5 *
     avg_over_time(chessguard_engine_evaluations_total[24h])`. This captures
     ingest stalls.

3. **Calibration drift**
   - Create an informational alert when the weekly offline evaluation produces
     a precision < 0.6 or recall < 0.5 using the harness output stored in
     `eval/metrics.json`. This requires human review of model performance.

## Dashboards

A Grafana dashboard should include the following panels:

- **Inference Throughput**: stacked rate of `chessguard_engine_evaluations_total`
  and `chessguard_engine_alerts_total` to visualise alert ratios.
- **Latency Heatmap**: heatmap of `chessguard_engine_latency_seconds` percentiles
  with annotations for deploys.
- **Service SLO**: `chessguard_service_latency_seconds` p95 and p99, plotted
  against the 1s SLO line.
- **Request Volume**: multi-series panel for
  `chessguard_service_requests_total` grouped by endpoint.
- **Calibration Curve**: image panel pointing at the latest
  `eval/calibration.png` artefact produced by the harness.

## Response Checklist

1. Confirm alert context with logs (`structlog` JSON payloads include component
   and tournament identifiers).
2. Inspect the Prometheus metrics for spikes in `chessguard_service_inflight_requests`
   which may indicate traffic bursts.
3. Re-run the offline harness (`python -m eval.run_all --output tmp/eval`) to
   validate current model behaviour.
4. If model degradation is confirmed, roll back to the previous model weights
   and re-run the harness before re-enabling alerts.
5. Document the incident in the on-call ticketing system including affected
   tournaments, mitigation steps, and follow-up actions.
