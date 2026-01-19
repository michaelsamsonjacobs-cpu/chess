"""Utility helpers for statistical calculations used across the ChessGuard backend."""

from __future__ import annotations

import math
from statistics import mean, median, pstdev
from typing import Iterable, List, Sequence


def safe_mean(values: Iterable[float]) -> float:
    """Return the mean of ``values`` or ``0.0`` when the input is empty."""

    values = list(values)
    if not values:
        return 0.0
    return float(mean(values))


def safe_median(values: Iterable[float]) -> float:
    """Return the median of ``values`` or ``0.0`` when the input is empty."""

    values = list(values)
    if not values:
        return 0.0
    return float(median(values))


def safe_pstdev(values: Iterable[float]) -> float:
    """Return the population standard deviation of ``values`` or ``0.0``."""

    values = list(values)
    if len(values) < 2:
        return 0.0
    return float(pstdev(values))


def logistic(x: float) -> float:
    """A numerically stable logistic function."""

    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def variance(values: Iterable[float]) -> float:
    """Return the population variance of ``values`` or ``0.0`` when empty."""

    values = list(values)
    if not values:
        return 0.0
    m = safe_mean(values)
    return float(sum((x - m) ** 2 for x in values) / len(values))


def covariance(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Return the population covariance for two equally sized sequences."""

    if len(xs) != len(ys):
        raise ValueError("Sequences must be the same length for covariance.")
    if not xs:
        return 0.0
    mean_x = safe_mean(xs)
    mean_y = safe_mean(ys)
    return float(sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs))


def linear_regression_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Return slope for a simple linear regression of ``ys`` on ``xs``."""

    if len(xs) != len(ys):
        raise ValueError("Sequences must be the same length for regression.")
    var_x = variance(xs)
    if var_x == 0:
        return 0.0
    return covariance(xs, ys) / var_x


def log_normal_variance(values: Iterable[float]) -> float:
    """Compute the variance of the log-transformed values (natural log)."""

    filtered: List[float] = [math.log(x) for x in values if x > 0]
    if len(filtered) < 2:
        return 0.0
    return variance(filtered)


def normalized_score(value: float, low: float, high: float) -> float:
    """Normalize ``value`` between 0 and 1 given bounds inclusive of extremes."""

    if high <= low:
        return 0.0
    clipped = max(min(value, high), low)
    return (clipped - low) / (high - low)

