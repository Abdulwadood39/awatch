"""Correlate stdlib logging with request_id via contextvars."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from monitorit.awatch.core.context import get_request_id

_BUFFER: dict[str, list[dict[str, Any]]] = {}


class RequestLogHandler(logging.Handler):
    """Captures log records emitted during a request into an in-memory buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        rid = get_request_id()
        if not rid:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
        }
        _BUFFER.setdefault(rid, []).append(entry)


def install_log_capture(level: int = logging.INFO) -> RequestLogHandler:
    handler = RequestLogHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    # Avoid duplicate handlers on re-init
    for h in list(root.handlers):
        if isinstance(h, RequestLogHandler):
            root.removeHandler(h)
    root.addHandler(handler)
    return handler


def pop_logs(request_id: str) -> list[dict[str, Any]]:
    return _BUFFER.pop(request_id, [])


def clear_logs() -> None:
    _BUFFER.clear()
