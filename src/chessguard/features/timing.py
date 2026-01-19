"""Timing feature extraction utilities."""

from __future__ import annotations

from typing import Dict, Iterable, List

from ..data.telemetry import SessionTelemetry


def _ratio(predicate, values: Iterable[float]) -> float:
    total = 0
    match = 0
    for value in values:
        total += 1
        if predicate(value):
            match += 1
    return match / total if total else 0.0


def _differences(values: List[float]) -> List[float]:
    return [b - a for a, b in zip(values, values[1:])]


def compute_timing_features(telemetry: SessionTelemetry) -> Dict[str, float]:
    """Compute descriptive statistics from move timing telemetry."""

    if not telemetry.entries:
        return {
            "avg_time": 0.0,
            "avg_time_white": 0.0,
            "avg_time_black": 0.0,
            "std_time": 0.0,
            "long_pause_rate": 0.0,
            "short_burst_rate": 0.0,
            "pace_balance": 0.0,
            "burstiness": 0.0,
            "tempo_shift_score": 0.0,
        }

    durations = [entry.seconds for entry in telemetry.entries]
    avg_time = sum(durations) / len(durations)
    std_time = telemetry.stdev()

    white_times = [entry.seconds for entry in telemetry.entries if entry.player == "white"]
    black_times = [entry.seconds for entry in telemetry.entries if entry.player == "black"]
    avg_time_white = sum(white_times) / len(white_times) if white_times else 0.0
    avg_time_black = sum(black_times) / len(black_times) if black_times else 0.0

    long_pause_rate = _ratio(lambda value: value >= 60.0, durations)
    short_burst_rate = _ratio(lambda value: value <= 5.0, durations)

    diffs = _differences(durations)
    tempo_shift_score = sum(abs(delta) for delta in diffs) / len(diffs) if diffs else 0.0

    burstiness = (max(durations) - min(durations)) / (avg_time + 1e-6)

    return {
        "avg_time": avg_time,
        "avg_time_white": avg_time_white,
        "avg_time_black": avg_time_black,
        "std_time": std_time,
        "long_pause_rate": long_pause_rate,
        "short_burst_rate": short_burst_rate,
        "pace_balance": avg_time_white - avg_time_black,
        "burstiness": burstiness,
        "tempo_shift_score": tempo_shift_score,
    }
