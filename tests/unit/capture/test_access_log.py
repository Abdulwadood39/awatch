"""Tests for uvicorn access-log quieting."""

from __future__ import annotations

import logging

from monitorit.awatch.capture.access_log import QuietAccessLogFilter, install_quiet_access_logs


def _record(msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_quiet_filter_drops_dashboard_and_health() -> None:
    filt = QuietAccessLogFilter(["/__awatch", "/health"])
    assert filt.filter(_record('127.0.0.1:1 - "GET /__awatch/ HTTP/1.1" 200 OK')) is False
    assert filt.filter(_record('127.0.0.1:1 - "GET /__awatch/api/overview HTTP/1.1" 200 OK')) is False
    assert filt.filter(_record('127.0.0.1:1 - "GET /health HTTP/1.1" 200 OK')) is False
    assert filt.filter(_record('127.0.0.1:1 - "POST /chat HTTP/1.1" 200 OK')) is True
    assert filt.filter(_record('127.0.0.1:1 - "GET / HTTP/1.1" 200 OK')) is True


def test_quiet_filter_does_not_match_prefix_siblings() -> None:
    filt = QuietAccessLogFilter(["/health"])
    assert filt.filter(_record('127.0.0.1:1 - "GET /healthcare HTTP/1.1" 200 OK')) is True
    assert filt.filter(_record('127.0.0.1:1 - "GET /healthz HTTP/1.1" 200 OK')) is True


def test_install_quiet_access_logs_idempotent() -> None:
    access = logging.getLogger("uvicorn.access")
    before = list(access.filters)
    try:
        a = install_quiet_access_logs(dashboard_path="/__awatch", extra_paths=["/health"])
        b = install_quiet_access_logs(dashboard_path="/__awatch", extra_paths=["/health"])
        assert a is b
        assert sum(1 for f in access.filters if isinstance(f, QuietAccessLogFilter)) >= 1
    finally:
        access.filters = before
