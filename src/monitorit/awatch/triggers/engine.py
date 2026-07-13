"""Trigger evaluation engine with cooldown."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from monitorit.awatch.storage.models import RequestRecord, TriggerHistoryRecord
from monitorit.awatch.storage.queue import WriteQueue
from monitorit.awatch.triggers.events import TriggerEvent
from monitorit.awatch.triggers.rules import Trigger

logger = logging.getLogger("awatch.triggers")


class TriggerEngine:
    def __init__(self, triggers: list[Trigger], queue: WriteQueue) -> None:
        self.triggers = list(triggers or [])
        self.queue = queue
        self._last_fired: dict[str, float] = {}

    async def handle_request(self, record: RequestRecord) -> None:
        stats: dict[str, Any] = {}
        for trigger in self.triggers:
            try:
                if not trigger.when(record, stats):
                    continue
            except Exception as exc:  # noqa: BLE001
                logger.exception("trigger condition error: %s", exc)
                continue

            fp = f"{trigger.name}:{record.route or record.path}:{record.status_code}"
            now = time.monotonic()
            last = self._last_fired.get(fp, 0.0)
            if now - last < trigger.cooldown_seconds():
                continue
            self._last_fired[fp] = now

            event = TriggerEvent(
                kind="request",
                fingerprint=fp,
                message=(
                    f"{trigger.name}: {record.method} {record.path} "
                    f"→ {record.status_code} in {record.duration_ms:.1f}ms"
                ),
                details={
                    "request_id": record.request_id,
                    "method": record.method,
                    "path": record.path,
                    "route": record.route,
                    "status_code": record.status_code,
                    "duration_ms": record.duration_ms,
                    "consumer_id": record.consumer_id,
                    "categories": record.categories,
                },
            )
            for action in trigger.actions():
                success = True
                message = "ok"
                try:
                    result = action(event)
                    if hasattr(result, "__await__"):
                        await result
                except Exception as exc:  # noqa: BLE001
                    success = False
                    message = str(exc)
                    logger.exception("trigger action failed: %s", exc)
                self.queue.enqueue_trigger(
                    TriggerHistoryRecord(
                        trigger_name=trigger.name,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        success=success,
                        message=message,
                        fingerprint=fp,
                        details=event.details,
                    )
                )
