"""Timeline bucket grain selection and zero-filled series for charts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

Grain = Literal["minute", "hour", "day"]

_TRUNC: dict[Grain, int] = {"minute": 16, "hour": 13, "day": 10}


def timeline_grain(hours: int) -> Grain:
    """Pick chart resolution from the selected window."""
    if hours <= 1:
        return "minute"
    if hours <= 48:
        return "hour"
    return "day"


def bucket_sql_len(grain: Grain) -> int:
    return _TRUNC[grain]


def timeline_unit_label(grain: Grain) -> str:
    return {"minute": "min", "hour": "hour", "day": "day"}[grain]


def _align_start(end: datetime, hours: int, grain: Grain) -> datetime:
    start = end - timedelta(hours=hours)
    if grain == "minute":
        return start.replace(second=0, microsecond=0)
    if grain == "hour":
        return start.replace(minute=0, second=0, microsecond=0)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def _fmt_bucket(dt: datetime, grain: Grain) -> str:
    if grain == "minute":
        return dt.strftime("%Y-%m-%dT%H:%M")
    if grain == "hour":
        return dt.strftime("%Y-%m-%dT%H")
    return dt.strftime("%Y-%m-%d")


def _step(grain: Grain) -> timedelta:
    if grain == "minute":
        return timedelta(minutes=1)
    if grain == "hour":
        return timedelta(hours=1)
    return timedelta(days=1)


def iter_buckets(
    hours: int,
    grain: Grain,
    *,
    end: datetime | None = None,
) -> list[str]:
    end = end or datetime.now(timezone.utc)
    cur = _align_start(end, hours, grain)
    step = _step(grain)
    out: list[str] = []
    # Include the current bucket even if we're mid-hour/day.
    limit = end + step
    guard = 0
    max_points = max(hours * 60, hours, 48) + 5
    while cur < limit and guard < max_points:
        out.append(_fmt_bucket(cur, grain))
        cur += step
        guard += 1
    return out


def fill_timeline(
    rows: list[dict[str, Any]],
    hours: int,
    *,
    grain: Grain | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return a continuous series with zero counts for empty buckets."""
    grain = grain or timeline_grain(hours)
    n = _TRUNC[grain]
    by: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("bucket") or "")[:n]
        if key:
            by[key] = row

    filled: list[dict[str, Any]] = []
    for bucket in iter_buckets(hours, grain, end=end):
        src = by.get(bucket) or {}
        filled.append(
            {
                "bucket": bucket,
                "count": int(src.get("count") or 0),
                "errors_4xx": int(src.get("errors_4xx") or 0),
                "errors": int(src.get("errors") or 0),
                "avg_ms": src.get("avg_ms"),
                "bytes_in": int(src.get("bytes_in") or 0) if src.get("bytes_in") is not None else 0,
                "bytes_out": int(src.get("bytes_out") or 0) if src.get("bytes_out") is not None else 0,
                "grain": grain,
            }
        )
    return filled


def fill_uptime_timeline(
    rows: list[dict[str, Any]],
    hours: int,
    *,
    grain: Grain | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Zero-filled uptime check series (total / ok_count per bucket)."""
    grain = grain or timeline_grain(hours)
    n = _TRUNC[grain]
    by: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("bucket") or "")[:n]
        if key:
            by[key] = row

    filled: list[dict[str, Any]] = []
    for bucket in iter_buckets(hours, grain, end=end):
        src = by.get(bucket) or {}
        total = int(src.get("total") or src.get("count") or 0)
        ok_count = int(src.get("ok_count") or 0)
        if ok_count > total:
            ok_count = total
        filled.append(
            {
                "bucket": bucket,
                "total": total,
                "ok_count": ok_count,
                "count": total,
                "grain": grain,
            }
        )
    return filled
