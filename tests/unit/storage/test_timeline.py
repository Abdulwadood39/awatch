"""Tests for traffic timeline grain + zero-fill."""

from __future__ import annotations

from datetime import datetime, timezone

from monitorit.awatch.storage.timeline import (
    fill_timeline,
    fill_uptime_timeline,
    timeline_grain,
)


def test_timeline_grain_adaptive():
    assert timeline_grain(1) == "minute"
    assert timeline_grain(24) == "hour"
    assert timeline_grain(48) == "hour"
    assert timeline_grain(168) == "day"


def test_fill_timeline_hourly_zeros():
    end = datetime(2026, 7, 30, 12, 30, tzinfo=timezone.utc)
    rows = [
        {"bucket": "2026-07-30T10", "count": 5, "errors": 1, "errors_4xx": 0, "avg_ms": 12.5},
        {"bucket": "2026-07-30T12", "count": 2, "errors": 0, "errors_4xx": 0, "avg_ms": 8},
    ]
    filled = fill_timeline(rows, 3, grain="hour", end=end)
    assert len(filled) >= 3
    by = {r["bucket"]: r for r in filled}
    assert by["2026-07-30T10"]["count"] == 5
    assert by["2026-07-30T10"]["errors"] == 1
    assert by["2026-07-30T11"]["count"] == 0
    assert by["2026-07-30T12"]["count"] == 2
    assert all(r["grain"] == "hour" for r in filled)


def test_fill_uptime_timeline():
    end = datetime(2026, 7, 30, 12, 30, tzinfo=timezone.utc)
    rows = [
        {"bucket": "2026-07-30T10", "total": 4, "ok_count": 3},
        {"bucket": "2026-07-30T12", "total": 2, "ok_count": 2},
    ]
    filled = fill_uptime_timeline(rows, 3, grain="hour", end=end)
    by = {r["bucket"]: r for r in filled}
    assert by["2026-07-30T10"]["total"] == 4
    assert by["2026-07-30T10"]["ok_count"] == 3
    assert by["2026-07-30T11"]["total"] == 0
    assert by["2026-07-30T12"]["ok_count"] == 2
