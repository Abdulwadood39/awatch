"""Optional dependency / outbound HTTP instrumentation."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from monitorit.awatch.core.context import (
    add_span,
    bump_outbound_count,
    get_outbound_count,
    get_request_id,
)
from monitorit.awatch.core.constants import MAX_BODY_BYTES
from monitorit.awatch.storage.models import RequestRecord


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


def _truncate(raw: str | bytes | None, max_bytes: int) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = str(raw)
    else:
        text = str(raw)
    if len(text.encode("utf-8")) > max_bytes:
        return text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore") + "…"
    return text


def _enqueue_outbound(
    *,
    queue: Any,
    config: Any,
    privacy: Any,
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    request_headers: dict[str, str] | None,
    response_headers: dict[str, str] | None,
    request_body: str | None,
    response_body: str | None,
    exception: str | None = None,
) -> None:
    parent_id = get_request_id()
    if not parent_id:
        return
    if get_outbound_count() >= int(getattr(config, "max_outbound_per_request", 50) or 50):
        return
    bump_outbound_count()

    max_bytes = int(getattr(config, "max_body_bytes", MAX_BODY_BYTES) or MAX_BODY_BYTES)
    req_headers = None
    res_headers = None
    req_body = None
    res_body = None
    if getattr(config, "log_request_headers", False) and request_headers:
        req_headers = privacy.mask_headers(dict(request_headers))
    if getattr(config, "log_response_headers", False) and response_headers:
        res_headers = privacy.mask_headers(dict(response_headers))
    if getattr(config, "log_request_body", False) and request_body is not None:
        req_body = privacy.mask_body(_truncate(request_body, max_bytes) or "")
    if getattr(config, "log_response_body", False) and response_body is not None:
        res_body = privacy.mask_body(_truncate(response_body, max_bytes) or "")

    record = RequestRecord(
        request_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        method=method.upper(),
        path=url,
        route=url,
        status_code=int(status_code),
        duration_ms=round(float(duration_ms), 3),
        request_headers=req_headers,
        response_headers=res_headers,
        request_body=req_body if isinstance(req_body, str) or req_body is None else str(req_body),
        response_body=res_body if isinstance(res_body, str) or res_body is None else str(res_body),
        exception=exception,
        direction="outbound",
        parent_request_id=parent_id,
    )
    queue.enqueue_request(record)


def instrument_httpx(
    *,
    queue: Any | None = None,
    config: Any | None = None,
    privacy: Any | None = None,
) -> None:
    """Monkey-patch httpx clients for outbound request rows (and legacy spans if no queue)."""
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return

    store_rows = queue is not None and config is not None and privacy is not None

    def _capture(request: Any, response: Any | None, duration_ms: float, exc: BaseException | None) -> None:
        method = getattr(request, "method", "GET")
        url = str(getattr(request, "url", ""))
        status = int(getattr(response, "status_code", 0) or 0) if response is not None else 0
        if not store_rows:
            record_span("http", f"{method} {url}", duration_ms, status_code=status or None)
            return
        req_headers = dict(getattr(request, "headers", {}) or {})
        res_headers = dict(getattr(response, "headers", {}) or {}) if response is not None else None
        req_body = None
        res_body = None
        try:
            content = getattr(request, "content", None)
            if content:
                req_body = content if isinstance(content, (bytes, str)) else None
        except Exception:  # noqa: BLE001
            req_body = None
        if response is not None:
            try:
                # Prefer already-read content without consuming stream twice
                res_body = getattr(response, "_content", None) or getattr(response, "content", None)
            except Exception:  # noqa: BLE001
                res_body = None
        _enqueue_outbound(
            queue=queue,
            config=config,
            privacy=privacy,
            method=method,
            url=url,
            status_code=status,
            duration_ms=duration_ms,
            request_headers=req_headers,
            response_headers=res_headers,
            request_body=_truncate(req_body, getattr(config, "max_body_bytes", MAX_BODY_BYTES))
            if req_body is not None
            else None,
            response_body=_truncate(res_body, getattr(config, "max_body_bytes", MAX_BODY_BYTES))
            if res_body is not None
            else None,
            exception=str(exc) if exc else None,
        )

    if not getattr(httpx.AsyncClient, "_awatch_patched", False):
        original_async = httpx.AsyncClient.send

        async def async_send(self, request, *args, **kwargs):  # noqa: ANN001
            start = time.perf_counter()
            response = None
            exc: BaseException | None = None
            try:
                response = await original_async(self, request, *args, **kwargs)
                return response
            except BaseException as e:  # noqa: BLE001
                exc = e
                raise
            finally:
                _capture(request, response, (time.perf_counter() - start) * 1000, exc)

        httpx.AsyncClient.send = async_send  # type: ignore[method-assign]
        httpx.AsyncClient._awatch_patched = True  # type: ignore[attr-defined]

    if not getattr(httpx.Client, "_awatch_patched", False):
        original_sync = httpx.Client.send

        def sync_send(self, request, *args, **kwargs):  # noqa: ANN001
            start = time.perf_counter()
            response = None
            exc: BaseException | None = None
            try:
                response = original_sync(self, request, *args, **kwargs)
                return response
            except BaseException as e:  # noqa: BLE001
                exc = e
                raise
            finally:
                _capture(request, response, (time.perf_counter() - start) * 1000, exc)

        httpx.Client.send = sync_send  # type: ignore[method-assign]
        httpx.Client._awatch_patched = True  # type: ignore[attr-defined]
