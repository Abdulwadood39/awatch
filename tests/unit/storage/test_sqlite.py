"""SQLite storage tests."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from monitorit.awatch.storage.models import RequestRecord
from monitorit.awatch.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_sqlite_roundtrip(tmp_path: Path):
    db = tmp_path / "t.db"
    store = SQLiteStorage(db)
    await store.setup()
    rec = RequestRecord(
        request_id="abc",
        timestamp=datetime.now(timezone.utc).isoformat(),
        method="GET",
        path="/x",
        route="/x",
        status_code=200,
        duration_ms=5.5,
        categories=["demo"],
    )
    await store.insert_request(rec)
    got = await store.get_request("abc")
    assert got is not None
    assert got["status_code"] == 200
    stats = await store.endpoint_stats(hours=24)
    assert stats[0]["count"] == 1
    await store.close()
