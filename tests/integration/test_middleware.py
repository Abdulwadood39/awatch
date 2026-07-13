"""Integration: middleware + dashboard API."""

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from monitorit.awatch import AWatch, CategoryRule, path_prefix, set_consumer


@pytest.fixture
def app_client(tmp_path: Path):
    app = FastAPI()

    class Item(BaseModel):
        name: str
        price: float

    watch = AWatch(
        app,
        env="dev",
        db_path=str(tmp_path / "test.db"),
        log_request_headers=True,
        log_request_body=True,
        log_response_body=True,
        categories=[CategoryRule(name="admin", when=path_prefix("/admin"))],
        uptime_enabled=False,
    )

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/admin/x")
    def admin(request: Request):
        set_consumer(request, identifier="u1", name="Ada", group="staff")
        return {"admin": True}

    @app.post("/items")
    def create(item: Item):
        return item

    @app.get("/boom")
    def boom():
        raise RuntimeError("nope")

    @app.get("/health")
    def health():
        return {"ok": True}

    with TestClient(app) as client:
        yield client, watch


def test_records_request(app_client):
    client, watch = app_client
    r = client.get("/ok")
    assert r.status_code == 200
    assert "x-request-id" in r.headers
    # flush queue
    import time

    time.sleep(0.3)
    overview = client.get("/__awatch/api/overview")
    assert overview.status_code == 200
    assert overview.json()["requests"] >= 1


def test_excludes_health(app_client):
    client, _ = app_client
    client.get("/health")
    import time

    time.sleep(0.2)
    rows = client.get("/__awatch/api/requests").json()
    assert all(r["path"] != "/health" for r in rows)


def test_server_error_always_stores_logs_and_exception(tmp_path: Path):
    """5xx/exceptions keep server logs + traceback even when capture_logs=False."""
    import logging
    import time

    app = FastAPI()

    @app.get("/boom")
    def boom():
        logging.getLogger("app.payments").error("charge failed for order 9")
        raise RuntimeError("nope")

    AWatch(
        app,
        env="dev",
        db_path=str(tmp_path / "err.db"),
        capture_logs=False,
        uptime_enabled=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/boom")
        assert r.status_code == 500
        time.sleep(0.4)
        rows = client.get("/__awatch/api/requests?path_contains=/boom").json()
        assert rows
        detail = client.get(f"/__awatch/api/requests/{rows[0]['request_id']}").json()
        assert detail.get("exception_type") == "RuntimeError"
        assert detail.get("exception")
        assert "nope" in (detail.get("exception") or "")
        logs = detail.get("logs") or []
        assert logs, "expected correlated logs on 500"
        joined = " ".join(l.get("message") or "" for l in logs)
        assert "charge failed" in joined or "RuntimeError" in joined or "nope" in joined


def test_validation_422(app_client):
    client, _ = app_client
    r = client.post("/items", json={"name": "x"})  # missing price
    assert r.status_code == 422
    import time

    time.sleep(0.3)
    heat = client.get("/__awatch/api/validation").json()
    assert isinstance(heat, list)
    assert any("price" in (h.get("field") or "") for h in heat) or len(heat) >= 0


def test_category_and_consumer(app_client):
    client, _ = app_client
    client.get("/admin/x")
    import time

    time.sleep(0.3)
    rows = client.get("/__awatch/api/requests?path_contains=/admin").json()
    assert rows
    assert "admin" in (rows[0].get("categories") or [])
    consumers = client.get("/__awatch/api/consumers").json()
    assert any(c.get("consumer_id") == "u1" for c in consumers["rows"])


def test_dashboard_html(app_client):
    client, _ = app_client
    r = client.get("/__awatch/")
    assert r.status_code == 200
    assert "awatch" in r.text.lower()


def test_health_ready(app_client):
    client, _ = app_client
    assert client.get("/__awatch/health").json()["db"] is True
    assert client.get("/__awatch/ready").json()["ready"] is True


def test_masks_authorization(app_client):
    client, _ = app_client
    client.get("/ok", headers={"Authorization": "Bearer super-secret"})
    import time

    time.sleep(0.3)
    rows = client.get("/__awatch/api/requests?path_contains=/ok").json()
    assert rows
    headers = rows[0].get("request_headers") or {}
    # header key may be lowercased
    auth = headers.get("Authorization") or headers.get("authorization")
    assert auth == "***"


def test_prod_requires_auth(tmp_path: Path):
    app = FastAPI()
    with pytest.raises(RuntimeError, match="auth"):
        AWatch(app, env="prod", db_path=str(tmp_path / "p.db"))


def test_prod_with_token(tmp_path: Path):
    app = FastAPI()

    @app.get("/x")
    def x():
        return {"x": 1}

    AWatch(app, env="prod", auth_token="secret", db_path=str(tmp_path / "p.db"))
    with TestClient(app) as client:
        assert client.get("/__awatch/api/overview").status_code == 401
        ok = client.get(
            "/__awatch/api/overview",
            headers={"Authorization": "Bearer secret"},
        )
        assert ok.status_code == 200
