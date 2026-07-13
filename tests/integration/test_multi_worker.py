"""Queue concurrency smoke test."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from awatch.storage.models import RequestRecord
from awatch.storage.queue import WriteQueue
from awatch.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_queue_handles_burst(tmp_path: Path):
    store = SQLiteStorage(tmp_path / "q.db")
    await store.setup()
    q = WriteQueue(store, max_requests=1000, retention_hours=24, prune_every=50)
    q.start()

    for i in range(50):
        ok = q.enqueue_request(
            RequestRecord(
                request_id=f"id-{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                method="GET",
                path=f"/n/{i}",
                route="/n/{i}",
                status_code=200,
                duration_ms=1.0,
            )
        )
        assert ok

    await asyncio.wait_for(q.queue.join(), timeout=5)
    await q.stop()
    counts = await store.counts()
    assert counts["requests"] == 50
    await store.close()
