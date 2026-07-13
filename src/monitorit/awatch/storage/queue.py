"""Single-writer async queue for non-blocking persistence."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from monitorit.awatch.storage.models import RequestRecord, TriggerHistoryRecord

logger = logging.getLogger("awatch.storage.queue")


class WriteQueue:
    """Buffers writes and flushes them on a dedicated asyncio task."""

    def __init__(
        self,
        storage: Any,
        *,
        maxsize: int = 10_000,
        prune_every: int = 100,
        max_requests: int = 10_000,
        retention_hours: int = 168,
        on_request: Callable[[RequestRecord], Awaitable[None]] | None = None,
    ) -> None:
        self.storage = storage
        self.queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self.max_requests = max_requests
        self.retention_hours = retention_hours
        self.prune_every = prune_every
        self.on_request = on_request
        self._task: asyncio.Task[None] | None = None
        self._writes = 0
        self.dropped = 0
        self.last_flush_age_s: float = 0.0
        self.last_error: str | None = None
        self._last_flush = asyncio.get_event_loop().time() if False else 0.0
        self.running = False

    @property
    def depth(self) -> int:
        return self.queue.qsize()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self.running = True
            self._task = asyncio.create_task(self._worker(), name="awatch-writer")

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self.queue.put_nowait(("__stop__", None))
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None

    def enqueue_request(self, record: RequestRecord) -> bool:
        try:
            self.queue.put_nowait(("request", record))
            return True
        except asyncio.QueueFull:
            self.dropped += 1
            return False

    def enqueue_trigger(self, record: TriggerHistoryRecord) -> bool:
        try:
            self.queue.put_nowait(("trigger", record))
            return True
        except asyncio.QueueFull:
            self.dropped += 1
            return False

    async def _worker(self) -> None:
        loop = asyncio.get_running_loop()
        self._last_flush = loop.time()
        while True:
            kind, payload = await self.queue.get()
            if kind == "__stop__":
                break
            try:
                if kind == "request":
                    await self.storage.insert_request(payload)
                    if self.on_request:
                        await self.on_request(payload)
                elif kind == "trigger":
                    await self.storage.insert_trigger_history(payload)
                self._writes += 1
                self._last_flush = loop.time()
                self.last_flush_age_s = 0.0
                if self._writes % self.prune_every == 0:
                    await self.storage.prune(self.max_requests, self.retention_hours)
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                logger.exception("awatch writer failed: %s", exc)
            finally:
                self.queue.task_done()
                self.last_flush_age_s = loop.time() - self._last_flush
