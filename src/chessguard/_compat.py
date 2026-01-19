"""Compatibility helpers that degrade gracefully when optional deps are missing."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any, Dict, Iterator, Tuple

try:  # pragma: no cover - optional dependency
    import structlog as _structlog
except Exception:  # pragma: no cover - optional dependency
    _structlog = None

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter as _Counter
    from prometheus_client import Gauge as _Gauge
    from prometheus_client import Histogram as _Histogram
    from prometheus_client import Summary as _Summary
    from prometheus_client import generate_latest as _generate_latest
except Exception:  # pragma: no cover - optional dependency
    _Counter = _Gauge = _Histogram = _Summary = None

    def _generate_latest() -> bytes:  # type: ignore[override]
        payload = []
        for metric in _REGISTERED_METRICS:
            payload.extend(metric.export_text())
        return "\n".join(payload).encode("utf-8")


_STRUCTLOG_CONFIGURED = False
_REGISTERED_METRICS: list["_NoopMetric"] = []


class _BoundLogger:
    """Minimal adapter mirroring the structlog API."""

    def __init__(self, logger: logging.Logger, context: Dict[str, Any]) -> None:
        self._logger = logger
        self._context = context

    def bind(self, **kwargs: Any) -> "_BoundLogger":
        combined = dict(self._context)
        combined.update(kwargs)
        return _BoundLogger(self._logger, combined)

    def info(self, event: str, **kwargs: Any) -> None:
        data = {**self._context, **kwargs}
        if data:
            self._logger.info("%s %s", event, data)
        else:
            self._logger.info("%s", event)

    def warning(self, event: str, **kwargs: Any) -> None:  # pragma: no cover - rarely used
        data = {**self._context, **kwargs}
        if data:
            self._logger.warning("%s %s", event, data)
        else:
            self._logger.warning("%s", event)

    def error(self, event: str, **kwargs: Any) -> None:  # pragma: no cover - rarely used
        data = {**self._context, **kwargs}
        if data:
            self._logger.error("%s %s", event, data)
        else:
            self._logger.error("%s", event)

    def debug(self, event: str, **kwargs: Any) -> None:  # pragma: no cover - rarely used
        data = {**self._context, **kwargs}
        if data:
            self._logger.debug("%s %s", event, data)
        else:
            self._logger.debug("%s", event)


def configure_structlog(level: int = logging.INFO) -> None:
    """Best-effort structlog configuration."""

    global _STRUCTLOG_CONFIGURED
    if _STRUCTLOG_CONFIGURED:
        return

    logging.basicConfig(level=level)
    if _structlog is not None:
        _structlog.configure(
            processors=[
                _structlog.processors.TimeStamper(fmt="iso"),
                _structlog.stdlib.add_log_level,
                _structlog.stdlib.PositionalArgumentsFormatter(),
                _structlog.processors.StackInfoRenderer(),
                _structlog.processors.format_exc_info,
                _structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            wrapper_class=_structlog.make_filtering_bound_logger(level),
            cache_logger_on_first_use=True,
        )
    _STRUCTLOG_CONFIGURED = True


def get_logger(name: str, **context: Any):
    """Return a structlog-like logger even when structlog is absent."""

    if _structlog is not None:
        configure_structlog()
        return _structlog.get_logger(name).bind(**context)
    return _BoundLogger(logging.getLogger(name), context)


class _NoopMetric:
    """Fallback metric with a matching API to Prometheus objects."""

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Tuple[str, ...],
        metric_type: str,
    ) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self.metric_type = metric_type
        self._values: Dict[Tuple[Any, ...], float] = {}
        self._current_labels: Tuple[Any, ...] = ()
        if not labelnames:
            self._values[()] = 0.0
        _REGISTERED_METRICS.append(self)

    def _active_key(self) -> Tuple[Any, ...]:
        if not self.labelnames:
            return ()
        if not self._current_labels:
            key = tuple("" for _ in self.labelnames)
            self._values.setdefault(key, 0.0)
            self._current_labels = key
        return self._current_labels

    def labels(self, **kwargs: Any) -> "_NoopMetric":
        if set(kwargs.keys()) != set(self.labelnames):
            raise ValueError(
                f"Expected labels {self.labelnames!r}, received {tuple(kwargs.keys())!r}"
            )
        key = tuple(kwargs[name] for name in self.labelnames)
        self._values.setdefault(key, 0.0)
        self._current_labels = key
        return self

    def inc(self, amount: float = 1.0, *_: Any, **__: Any) -> None:
        key = self._active_key()
        self._values[key] = self._values.get(key, 0.0) + float(amount)

    def dec(self, amount: float = 1.0, *_: Any, **__: Any) -> None:
        key = self._active_key()
        self._values[key] = self._values.get(key, 0.0) - float(amount)

    def observe(self, value: float, *_: Any, **__: Any) -> None:
        key = self._active_key()
        self._values[key] = float(value)

    def set(self, value: float, *_: Any, **__: Any) -> None:
        key = self._active_key()
        self._values[key] = float(value)

    @contextlib.contextmanager
    def time(self) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(time.perf_counter() - start)

    def export_text(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.documentation}",
            f"# TYPE {self.name} {self.metric_type}",
        ]
        if not self._values:
            self._values[self._active_key()] = 0.0
        for key, value in self._values.items():
            if self.labelnames:
                labels = ",".join(
                    f'{name}="{label}"' for name, label in zip(self.labelnames, key)
                )
                lines.append(f"{self.name}{{{labels}}} {value}")
            else:
                lines.append(f"{self.name} {value}")
        return lines


def _build_noop_metric(metric_type: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _NoopMetric:
    if not args:
        raise TypeError("Metric name is required")
    name = str(args[0])
    documentation = str(args[1]) if len(args) > 1 else ""
    if len(args) > 2:
        labelnames = tuple(args[2]) if args[2] else tuple()
    else:
        labelnames = tuple(kwargs.get("labelnames", ()))
    return _NoopMetric(name, documentation, labelnames, metric_type)


def Counter(*args: Any, **kwargs: Any):  # noqa: N802 - mirror prometheus API
    if _Counter is not None:
        return _Counter(*args, **kwargs)
    return _build_noop_metric("counter", args, kwargs)


def Gauge(*args: Any, **kwargs: Any):  # noqa: N802 - mirror prometheus API
    if _Gauge is not None:
        return _Gauge(*args, **kwargs)
    return _build_noop_metric("gauge", args, kwargs)


def Histogram(*args: Any, **kwargs: Any):  # noqa: N802 - mirror prometheus API
    if _Histogram is not None:
        return _Histogram(*args, **kwargs)
    return _build_noop_metric("histogram", args, kwargs)


def Summary(*args: Any, **kwargs: Any):  # noqa: N802 - mirror prometheus API
    if _Summary is not None:
        return _Summary(*args, **kwargs)
    return _build_noop_metric("summary", args, kwargs)


def generate_latest() -> bytes:
    return _generate_latest()


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    "configure_structlog",
    "generate_latest",
    "get_logger",
]
