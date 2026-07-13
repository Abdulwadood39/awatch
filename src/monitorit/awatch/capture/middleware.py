"""ASGI middleware that captures request/response metadata."""

from __future__ import annotations

import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import parse_qs

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from monitorit.awatch.analytics.errors import fingerprint_exception
from monitorit.awatch.analytics.validation import extract_validation_errors
from monitorit.awatch.capture.logging_bridge import install_log_capture, pop_logs
from monitorit.awatch.capture.sampling import should_sample_request
from monitorit.awatch.core.constants import REQUEST_ID_HEADER
from monitorit.awatch.core.context import (
    get_categories,
    get_consumer,
    get_spans,
    reset_request_context,
    set_categories,
    set_request_id,
)
from monitorit.awatch.core.config import AWatchConfig
from monitorit.awatch.privacy.mask import PrivacyFilter
from monitorit.awatch.storage.models import RequestRecord
from monitorit.awatch.storage.queue import WriteQueue


def _client_ip(scope: Scope, headers: Headers) -> str | None:
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return None


def _route_template(scope: Scope) -> str | None:
    route = scope.get("route")
    if route is not None and hasattr(route, "path"):
        return getattr(route, "path", None)
    # Starlette may set endpoint later; try path from router match
    for key in ("path_template", "raw_path"):
        if key in scope:
            val = scope[key]
            if isinstance(val, bytes):
                return val.decode()
            return str(val)
    return None


class AWatchMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        config: AWatchConfig,
        privacy: PrivacyFilter,
        queue: WriteQueue,
        category_engine: Any | None = None,
        trigger_engine: Any | None = None,
        consumer_extractor: Any | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.privacy = privacy
        self.queue = queue
        self.category_engine = category_engine
        self.trigger_engine = trigger_engine
        self.consumer_extractor = consumer_extractor

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self.privacy.should_exclude(path):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get(REQUEST_ID_HEADER.lower()) or str(uuid.uuid4())
        set_request_id(request_id)

        method = scope.get("method", "GET")
        query_string = scope.get("query_string", b"").decode("latin-1")
        raw_query = {
            k: v[0] if len(v) == 1 else v
            for k, v in parse_qs(query_string, keep_blank_values=True).items()
        }

        request_body = b""
        request_headers_raw = {k.decode(): v.decode(errors="replace") for k, v in scope.get("headers", [])}

        async def receive_wrapper() -> Message:
            nonlocal request_body
            message = await receive()
            if message["type"] == "http.request" and self.config.log_request_body:
                body = message.get("body", b"")
                if body and len(request_body) < self.config.max_body_bytes:
                    remain = self.config.max_body_bytes - len(request_body)
                    request_body += body[:remain]
            return message

        status_code = 500
        response_headers: dict[str, str] = {}
        response_body = b""
        exception_text: str | None = None
        exception_type: str | None = None
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_headers, response_body
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                hdrs = Headers(raw=message.get("headers", []))
                response_headers = {k: v for k, v in hdrs.items()}
                # inject request id
                headers_list = list(message.get("headers", []))
                headers_list.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message = {**message, "headers": headers_list}
            elif message["type"] == "http.response.body" and self.config.log_response_body:
                body = message.get("body", b"")
                if body and len(response_body) < self.config.max_body_bytes:
                    remain = self.config.max_body_bytes - len(response_body)
                    response_body += body[:remain]
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as exc:
            exception_type = type(exc).__name__
            exception_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            status_code = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            try:
                await self._finalize(
                    request_id=request_id,
                    method=method,
                    path=path,
                    scope=scope,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    headers=headers,
                    request_headers_raw=request_headers_raw,
                    response_headers=response_headers,
                    raw_query=raw_query,
                    request_body=request_body,
                    response_body=response_body,
                    exception_text=exception_text,
                    exception_type=exception_type,
                )
            finally:
                reset_request_context()

    async def _finalize(self, **kw: Any) -> None:
        if not self.config.enable_request_logging:
            # Still record lightweight metrics-style row without bodies
            pass

        if not should_sample_request(
            status_code=kw["status_code"],
            duration_ms=kw["duration_ms"],
            slow_threshold_ms=self.config.slow_threshold_ms,
            success_sample_rate=self.config.success_sample_rate,
        ):
            # Still drain the log buffer so memory does not grow
            pop_logs(kw["request_id"])
            return

        route = _route_template(kw["scope"]) or kw["path"]
        consumer = get_consumer() or kw["scope"].get("awatch_consumer") or {}
        if not consumer and self.consumer_extractor is not None:
            try:
                consumer = (
                    self.consumer_extractor.resolve(
                        method=kw["method"],
                        path=kw["path"],
                        headers=kw["request_headers_raw"],
                        query=kw["raw_query"],
                        body=kw["request_body"],
                    )
                    or {}
                )
            except Exception:  # noqa: BLE001
                consumer = {}

        # Categories
        categories: list[str] = []
        if self.category_engine is not None:
            try:
                categories = await self.category_engine.evaluate(
                    method=kw["method"],
                    path=kw["path"],
                    headers=kw["request_headers_raw"],
                    query=kw["raw_query"],
                    body=kw["request_body"],
                    consumer=consumer,
                )
            except Exception:  # noqa: BLE001
                categories = []
        set_categories(categories)

        validation_errors = []
        if kw["status_code"] == 422 and kw["response_body"]:
            validation_errors = extract_validation_errors(kw["response_body"])

        req_headers = None
        if self.config.log_request_headers:
            req_headers = self.privacy.mask_headers(kw["request_headers_raw"])

        resp_headers = None
        if self.config.log_response_headers:
            resp_headers = self.privacy.mask_headers(kw["response_headers"])

        query_params = None
        if self.config.log_query_params:
            query_params = self.privacy.mask_query(kw["raw_query"])

        req_body = None
        if self.config.log_request_body and kw["request_body"]:
            req_body = self.privacy.mask_body(kw["request_body"])

        resp_body = None
        if self.config.log_response_body and kw["response_body"]:
            resp_body = self.privacy.mask_body(kw["response_body"])

        logs = self._collect_logs(
            request_id=kw["request_id"],
            status_code=kw["status_code"],
            exception_type=kw.get("exception_type"),
            exception_text=kw.get("exception_text"),
        )
        spans = get_spans()

        # Always keep exception/traceback for 5xx so failures are diagnosable
        is_server_error = kw["status_code"] >= 500 or bool(kw.get("exception_type"))
        exc = kw["exception_text"] if (self.config.log_exception or is_server_error) else None
        exc_type = kw["exception_type"]
        fp = fingerprint_exception(exc_type, route, exc) if exc_type else None

        record = RequestRecord(
            request_id=kw["request_id"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=kw["method"],
            path=kw["path"],
            route=route,
            status_code=kw["status_code"],
            duration_ms=round(kw["duration_ms"], 3),
            client_ip=_client_ip(kw["scope"], kw["headers"]),
            user_agent=kw["headers"].get("user-agent"),
            request_size=len(kw["request_body"] or b""),
            response_size=len(kw["response_body"] or b""),
            query_params=query_params,
            request_headers=req_headers,
            response_headers=resp_headers,
            request_body=req_body,
            response_body=resp_body,
            exception=exc,
            exception_type=exc_type,
            consumer_id=consumer.get("identifier"),
            consumer_name=consumer.get("name"),
            consumer_group=consumer.get("group"),
            categories=categories,
            logs=logs,
            spans=spans,
            validation_errors=validation_errors,
            release=self.config.release,
            error_fingerprint=fp,
        )
        self.queue.enqueue_request(record)

        if self.trigger_engine is not None:
            try:
                await self.trigger_engine.handle_request(record)
            except Exception:  # noqa: BLE001
                pass

    def _collect_logs(
        self,
        *,
        request_id: str,
        status_code: int,
        exception_type: str | None,
        exception_text: str | None,
    ) -> list[dict[str, Any]]:
        """Persist correlated server logs for all requests when capture_logs is on,
        and **always** for 5xx / unhandled exceptions so failures are diagnosable.
        """
        buffered = pop_logs(request_id)
        is_server_error = status_code >= 500 or bool(exception_type)
        if not (self.config.capture_logs or is_server_error):
            return []

        logs = list(buffered)
        if is_server_error and exception_text:
            # Ensure the traceback is visible in the inspector even if the app
            # never logged anything itself.
            already = any(
                exception_type and exception_type in (e.get("message") or "") for e in logs
            )
            if not already:
                from datetime import datetime, timezone

                logs.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "ERROR",
                        "logger": "awatch.exception",
                        "message": exception_text[-8000:],  # cap size
                    }
                )
        return logs
