"""Trigger conditions (composable)."""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from awatch.storage.models import RequestRecord


@dataclass
class _And:
    left: Any
    right: Any

    def __call__(self, record: RequestRecord, stats: dict[str, Any]) -> bool:
        return bool(self.left(record, stats) and self.right(record, stats))

    def __and__(self, other: Any) -> _And:
        return _And(self, other)

    def __or__(self, other: Any) -> _Or:
        return _Or(self, other)


@dataclass
class _Or:
    left: Any
    right: Any

    def __call__(self, record: RequestRecord, stats: dict[str, Any]) -> bool:
        return bool(self.left(record, stats) or self.right(record, stats))

    def __and__(self, other: Any) -> _And:
        return _And(self, other)

    def __or__(self, other: Any) -> _Or:
        return _Or(self, other)


@dataclass
class _Cond:
    fn: Callable[[RequestRecord, dict[str, Any]], bool]

    def __call__(self, record: RequestRecord, stats: dict[str, Any]) -> bool:
        return self.fn(record, stats)

    def __and__(self, other: Any) -> _And:
        return _And(self, other)

    def __or__(self, other: Any) -> _Or:
        return _Or(self, other)


def status_in(codes: range | set[int] | list[int]) -> _Cond:
    code_set = set(codes)

    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        return record.status_code in code_set

    return _Cond(_fn)


def path_matches(pattern: str) -> _Cond:
    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        return fnmatch.fnmatch(record.path, pattern) or fnmatch.fnmatch(
            record.route or "", pattern
        )

    return _Cond(_fn)


def category_is(name: str) -> _Cond:
    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        return name in (record.categories or [])

    return _Cond(_fn)


def duration_above(ms: float) -> _Cond:
    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        return record.duration_ms >= ms

    return _Cond(_fn)


# Rolling window counters for error_rate_above
_window_buckets: dict[str, list[tuple[float, bool]]] = {}


def error_rate_above(
    rate: float,
    window: str = "5m",
    endpoint: str | None = None,
) -> _Cond:
    seconds = _parse_window(window)

    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        key = endpoint or (record.route or record.path)
        if endpoint and (record.route != endpoint and record.path != endpoint):
            # still record? only evaluate for matching endpoint
            ep = record.route or record.path
            if ep != endpoint and not fnmatch.fnmatch(record.path, endpoint):
                return False
        bucket_key = f"{key}"
        now = time.time()
        is_err = record.status_code >= 400
        arr = _window_buckets.setdefault(bucket_key, [])
        arr.append((now, is_err))
        cutoff = now - seconds
        _window_buckets[bucket_key] = [(t, e) for t, e in arr if t >= cutoff]
        arr = _window_buckets[bucket_key]
        if len(arr) < 5:
            return False
        err = sum(1 for _, e in arr if e)
        return (err / len(arr)) >= rate

    return _Cond(_fn)


def rpm_above(threshold: float, window: str = "1m") -> _Cond:
    """Fire when requests/minute in the rolling window exceeds threshold."""
    seconds = _parse_window(window)
    bucket: list[float] = []

    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        now = time.time()
        bucket.append(now)
        cutoff = now - seconds
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        rpm = len(bucket) / max(seconds / 60.0, 1e-6)
        stats["rpm"] = rpm
        return rpm >= threshold

    return _Cond(_fn)


def p95_above(ms: float, window: str = "5m", min_samples: int = 10) -> _Cond:
    seconds = _parse_window(window)
    samples: list[tuple[float, float]] = []

    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        now = time.time()
        samples.append((now, record.duration_ms))
        cutoff = now - seconds
        while samples and samples[0][0] < cutoff:
            samples.pop(0)
        if len(samples) < min_samples:
            return False
        vals = sorted(d for _, d in samples)
        idx = int(0.95 * (len(vals) - 1))
        p95 = vals[idx]
        stats["p95_ms"] = p95
        return p95 >= ms

    return _Cond(_fn)


def apdex_below(score: float, t_ms: float = 500.0, window: str = "5m", min_samples: int = 10) -> _Cond:
    seconds = _parse_window(window)
    samples: list[tuple[float, float]] = []

    def _fn(record: RequestRecord, stats: dict[str, Any]) -> bool:
        now = time.time()
        samples.append((now, record.duration_ms))
        cutoff = now - seconds
        while samples and samples[0][0] < cutoff:
            samples.pop(0)
        if len(samples) < min_samples:
            return False
        durs = [d for _, d in samples]
        satisfied = sum(1 for d in durs if d <= t_ms)
        tolerating = sum(1 for d in durs if t_ms < d <= 4 * t_ms)
        apdex = (satisfied + tolerating * 0.5) / len(durs)
        stats["apdex"] = apdex
        return apdex < score

    return _Cond(_fn)


def _parse_window(window: str) -> float:
    window = window.strip().lower()
    if window.endswith("ms"):
        return float(window[:-2]) / 1000.0
    if window.endswith("s"):
        return float(window[:-1])
    if window.endswith("m"):
        return float(window[:-1]) * 60.0
    if window.endswith("h"):
        return float(window[:-1]) * 3600.0
    return float(window)
