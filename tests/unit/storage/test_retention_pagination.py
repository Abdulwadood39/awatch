"""Retention and pagination storage tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitorit.awatch.storage.models import RequestRecord
from monitorit.awatch.storage.queue import WriteQueue
from monitorit.awatch.storage.sqlite import SQLiteStorage


def _record(rid: str, ts: str, *, direction: str = "inbound", parent: str | None = None) -> RequestRecord:
    return RequestRecord(
        request_id=rid,
        timestamp=ts,
        method="GET",
        path=f"/{rid}",
        route=f"/{rid}",
        status_code=200,
        duration_ms=1.0,
        direction=direction,
        parent_request_id=parent,
        request_body="SECRET_BODY",
        response_body="SECRET_RESP",
    )


@pytest.mark.asyncio
async def test_prune_age_and_max_requests(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "t.db")
    await storage.setup()
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=200)).isoformat()
    recent = now.isoformat()
    await storage.insert_request(_record("old", old))
    for i in range(5):
        await storage.insert_request(_record(f"r{i}", recent))
    await storage.prune(max_requests=3, retention_hours=168)
    page = await storage.list_requests(limit=50, offset=0, direction="all")
    assert page["total"] == 3
    assert all(i["request_id"] != "old" for i in page["items"])
    await storage.close()


@pytest.mark.asyncio
async def test_list_requests_summary_excludes_bodies(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "t.db")
    await storage.setup()
    await storage.insert_request(_record("a", datetime.now(timezone.utc).isoformat()))
    page = await storage.list_requests(limit=10, offset=0)
    assert "items" in page and "total" in page
    assert page["total"] == 1
    assert "request_body" not in page["items"][0]
    assert "response_body" not in page["items"][0]
    detail = await storage.get_request("a")
    assert detail["request_body"] == "SECRET_BODY"
    await storage.close()


@pytest.mark.asyncio
async def test_outbound_children_and_inbound_analytics(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "t.db")
    await storage.setup()
    ts = datetime.now(timezone.utc).isoformat()
    await storage.insert_request(_record("parent", ts))
    await storage.insert_request(
        _record("child", ts, direction="outbound", parent="parent")
    )
    children = await storage.list_outbound_for_parent("parent")
    assert len(children) == 1
    assert children[0]["request_id"] == "child"
    page = await storage.list_requests(limit=10, offset=0, direction="inbound")
    assert page["total"] == 1
    assert page["items"][0]["request_id"] == "parent"
    counts = await storage.counts()
    assert counts["requests"] == 1
    assert counts["requests_all"] == 2
    await storage.close()


@pytest.mark.asyncio
async def test_write_queue_configure_retention(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "t.db")
    await storage.setup()
    q = WriteQueue(storage, prune_every=1, max_requests=10, retention_hours=168)
    q.configure_retention(max_requests=5, retention_hours=24, prune_every=2)
    assert q.max_requests == 5
    assert q.retention_hours == 24
    assert q.prune_every == 2
    await storage.close()
