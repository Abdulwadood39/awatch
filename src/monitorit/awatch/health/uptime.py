"""Uptime monitoring: heartbeat buckets + synthetic HTTP checks."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("awatch.uptime")


class UptimeMonitor:
    """Background synthetic checks + heartbeat recording into storage."""

    def __init__(
        self,
        *,
        storage: Any,
        base_url: str = "http://127.0.0.1",
        path: str = "/health",
        interval_seconds: float = 60.0,
        expected_status: int = 200,
        timeout_seconds: float = 5.0,
        enabled: bool = True,
        on_failure: Callable[..., Any] | None = None,
    ) -> None:
        self.storage = storage
        self.base_url = base_url.rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"
        self.interval_seconds = max(10.0, float(interval_seconds))
        self.expected_status = expected_status
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled
        self.on_failure = on_failure
        self._task: asyncio.Task[None] | None = None
        self._hb_task: asyncio.Task[None] | None = None
        self._consecutive_failures = 0
        self.last_result: dict[str, Any] | None = None
        self._heartbeat_fn: Callable[[], float | None] | None = None

    def set_heartbeat_source(self, fn: Callable[[], float | None]) -> None:
        self._heartbeat_fn = fn

    def configure(
        self,
        *,
        path: str | None = None,
        interval_seconds: float | None = None,
        expected_status: int | None = None,
        enabled: bool | None = None,
        base_url: str | None = None,
    ) -> None:
        if path is not None:
            self.path = path if path.startswith("/") else f"/{path}"
        if interval_seconds is not None:
            self.interval_seconds = max(10.0, float(interval_seconds))
        if expected_status is not None:
            self.expected_status = int(expected_status)
        if enabled is not None:
            self.enabled = bool(enabled)
        if base_url is not None:
            self.base_url = base_url.rstrip("/")

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="awatch-uptime-synthetic")
        if self._hb_task is None:
            self._hb_task = asyncio.create_task(self._heartbeat_loop(), name="awatch-uptime-hb")

    async def stop(self) -> None:
        for task in (self._task, self._hb_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._hb_task = None

    async def record_external_ping(
        self, *, ok: bool = True, latency_ms: float | None = None, message: str | None = None
    ) -> None:
        await self.storage.insert_uptime_check(
            kind="external",
            ok=ok,
            latency_ms=latency_ms,
            status_code=200 if ok else None,
            message=message or "external ping",
            path=self.path,
        )

    async def run_check_once(self) -> dict[str, Any]:
        url = f"{self.base_url}{self.path}"
        start = time.perf_counter()
        ok = False
        status_code: int | None = None
        message = "ok"
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url)
                status_code = resp.status_code
                ok = status_code == self.expected_status
                if not ok:
                    message = f"expected {self.expected_status}, got {status_code}"
        except Exception as exc:  # noqa: BLE001
            # Fallback without httpx: urllib
            try:
                import urllib.request

                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    status_code = getattr(resp, "status", None) or resp.getcode()
                    ok = int(status_code) == self.expected_status
                    if not ok:
                        message = f"expected {self.expected_status}, got {status_code}"
            except Exception as exc2:  # noqa: BLE001
                message = str(exc2 or exc)
                ok = False
        latency_ms = (time.perf_counter() - start) * 1000
        result = {
            "ok": ok,
            "latency_ms": round(latency_ms, 2),
            "status_code": status_code,
            "message": message,
            "path": self.path,
            "kind": "synthetic",
        }
        self.last_result = result
        await self.storage.insert_uptime_check(
            kind="synthetic",
            ok=ok,
            latency_ms=result["latency_ms"],
            status_code=status_code,
            message=message,
            path=self.path,
        )
        if ok:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            if self.on_failure and self._consecutive_failures >= 2:
                try:
                    maybe = self.on_failure(result)
                    if hasattr(maybe, "__await__"):
                        await maybe
                except Exception:  # noqa: BLE001
                    logger.exception("uptime failure callback error")
        return result

    async def _loop(self) -> None:
        while True:
            try:
                if self.enabled:
                    await self.run_check_once()
            except Exception:  # noqa: BLE001
                logger.exception("synthetic uptime check failed")
            await asyncio.sleep(self.interval_seconds)

    async def _heartbeat_loop(self) -> None:
        """Record minute heartbeats based on last request age."""
        while True:
            try:
                age = self._heartbeat_fn() if self._heartbeat_fn else None
                # Consider up if we saw traffic in the last 2 minutes, or just started
                ok = age is None or age < 120
                await self.storage.insert_uptime_check(
                    kind="heartbeat",
                    ok=ok,
                    latency_ms=None,
                    status_code=None,
                    message=None if age is None else f"age_s={round(age, 1)}",
                    path=None,
                )
            except Exception:  # noqa: BLE001
                logger.exception("heartbeat uptime record failed")
            await asyncio.sleep(60.0)
