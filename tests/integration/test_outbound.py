"""Outbound httpx instrumentation tests."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from monitorit import awatch
from monitorit.awatch.capture.dependencies import instrument_httpx


def test_outbound_http_recorded_as_child(tmp_path: Path) -> None:
    app = FastAPI()
    awatch.AWatch(
        app,
        env="dev",
        db_path=str(tmp_path / "awatch.db"),
        instrument_outbound_http=True,
        uptime_enabled=False,
        quiet_access_logs=False,
    )

    # Force re-patch with a controllable transport layer after AWatch init
    watch = app.state.awatch
    httpx.AsyncClient._awatch_patched = False  # type: ignore[attr-defined]

    async def fake_send(self, request, *args, **kwargs):  # noqa: ANN001
        return Response(201, request=request, content=b'{"ok":true}')

    # Install fake first, then awatch wrapper
    httpx.AsyncClient.send = fake_send  # type: ignore[method-assign]
    instrument_httpx(queue=watch.queue, config=watch.config, privacy=watch.privacy)

    @app.get("/external")
    async def external():
        async with httpx.AsyncClient() as client:
            r = await client.get("https://example.com/api/escalate")
            return {"status": r.status_code}

    with TestClient(app) as client:
        resp = client.get("/external")
        assert resp.status_code == 200
        assert resp.json()["status"] == 201
        # allow writer queue to flush
        for _ in range(20):
            page = client.get("/__awatch/api/requests?path_contains=/external").json()
            if page.get("total", 0) >= 1:
                break
            time.sleep(0.05)
        assert page["total"] >= 1
        parent_id = page["items"][0]["request_id"]
        detail = None
        for _ in range(20):
            detail = client.get(f"/__awatch/api/requests/{parent_id}").json()
            if detail.get("outbound"):
                break
            time.sleep(0.05)
        assert detail is not None
        assert any("example.com" in (o.get("path") or "") for o in detail.get("outbound") or [])
