"""Silence uvicorn access logs for awatch dashboard / health probe traffic."""

from __future__ import annotations

import logging
import re
from typing import Iterable

# uvicorn: 127.0.0.1:1234 - "GET /path?x=1 HTTP/1.1" 200 OK
_ACCESS_PATH = re.compile(r'"[A-Z]+ ([^?\s"]+)')


class QuietAccessLogFilter(logging.Filter):
    """Drop uvicorn access lines whose request path is under a quiet prefix."""

    def __init__(self, prefixes: Iterable[str]) -> None:
        super().__init__()
        cleaned: list[str] = []
        for p in prefixes:
            p = (p or "").strip()
            if not p:
                continue
            if p != "/" and p.endswith("/"):
                p = p.rstrip("/")
            cleaned.append(p)
        self._prefixes = tuple(dict.fromkeys(cleaned))

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        match = _ACCESS_PATH.search(msg)
        if not match:
            return True
        path = match.group(1)
        for prefix in self._prefixes:
            if path == prefix or path.startswith(prefix + "/"):
                return False
        return True


def install_quiet_access_logs(
    *,
    dashboard_path: str = "/__awatch",
    extra_paths: Iterable[str] | None = None,
) -> QuietAccessLogFilter:
    """Attach a filter to ``uvicorn.access`` (idempotent per dashboard path)."""
    dash = (dashboard_path or "/__awatch").rstrip("/") or "/__awatch"
    prefixes = [dash]
    for p in extra_paths or ():
        p = (p or "").strip()
        if p:
            prefixes.append(p)

    access = logging.getLogger("uvicorn.access")
    for existing in list(access.filters):
        if isinstance(existing, QuietAccessLogFilter) and dash in existing._prefixes:
            return existing

    filt = QuietAccessLogFilter(prefixes)
    access.addFilter(filt)
    return filt
