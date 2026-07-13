"""Optional dependency / outbound timing instrumentation."""

from __future__ import annotations

import time
from typing import Any

from awatch.core.context import add_span, get_request_id


def record_span(kind: str, name: str, duration_ms: float, **extra: Any) -> None:
    if not get_request_id():
        return
    add_span({"kind": kind, "name": name, "duration_ms": round(duration_ms, 3), **extra})


def instrument_sqlalchemy(engine: Any) -> None:
    """Attach sync SQLAlchemy event listeners for query timing."""
    try:
        from sqlalchemy import event
    except ImportError as exc:  # pragma: no cover
        raise ImportError("SQLAlchemy is required for db_engine instrumentation") from exc

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        conn.info.setdefault("awatch_query_start", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        starts = conn.info.get("awatch_query_start", [])
        if not starts:
            return
        start = starts.pop()
        duration_ms = (time.perf_counter() - start) * 1000
        sql = statement if isinstance(statement, str) else str(statement)
        record_span("sql", sql[:200], duration_ms)


def instrument_httpx() -> None:
    """Monkey-patch httpx.AsyncClient.send for outbound timing (best-effort)."""
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return

    if getattr(httpx.AsyncClient, "_awatch_patched", False):
        return

    original = httpx.AsyncClient.send

    async def send(self, request, *args, **kwargs):  # noqa: ANN001
        start = time.perf_counter()
        try:
            response = await original(self, request, *args, **kwargs)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            record_span(
                "http",
                f"{request.method} {request.url}",
                duration_ms,
            )

    httpx.AsyncClient.send = send  # type: ignore[method-assign]
    httpx.AsyncClient._awatch_patched = True  # type: ignore[attr-defined]
