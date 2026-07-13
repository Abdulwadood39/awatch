"""Trigger condition + engine tests."""

from datetime import datetime, timezone

import pytest

from monitorit.awatch.storage.models import RequestRecord
from monitorit.awatch.storage.queue import WriteQueue
from monitorit.awatch.triggers import LogAction, Trigger, status_in
from monitorit.awatch.triggers.conditions import path_matches
from monitorit.awatch.triggers.engine import TriggerEngine


def _record(status=500, path="/payments/charge"):
    return RequestRecord(
        request_id="r1",
        timestamp=datetime.now(timezone.utc).isoformat(),
        method="GET",
        path=path,
        route=path,
        status_code=status,
        duration_ms=12.0,
    )


class FakeStorage:
    def __init__(self):
        self.triggers = []

    async def insert_trigger_history(self, record):
        self.triggers.append(record)

    async def insert_request(self, record):
        pass

    async def prune(self, *a, **k):
        pass


@pytest.mark.asyncio
async def test_trigger_fires_on_5xx(tmp_path):
    storage = FakeStorage()
    queue = WriteQueue(storage)
    queue.start()
    engine = TriggerEngine(
        [
            Trigger(
                name="pay",
                when=status_in(range(500, 600)) & path_matches("/payments/*"),
                then=LogAction(),
                cooldown="0s",
            )
        ],
        queue,
    )
    await engine.handle_request(_record())
    await queue.queue.join()
    await queue.stop()
    assert len(storage.triggers) >= 1
    assert storage.triggers[0].trigger_name == "pay"


def test_condition_path():
    cond = status_in({500}) & path_matches("/payments/*")
    assert cond(_record(), {})
    assert not cond(_record(status=200), {})
