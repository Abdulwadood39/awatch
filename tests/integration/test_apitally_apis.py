"""Uptime + traffic/performance API smoke tests."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from awatch import AWatch


def test_traffic_performance_uptime_apis(tmp_path: Path):
    app = FastAPI()

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    AWatch(
        app,
        env="dev",
        db_path=str(tmp_path / "u.db"),
        allow_ui_config=True,
        uptime_enabled=False,
    )
    with TestClient(app) as client:
        client.get("/ok")
        import time

        time.sleep(0.3)

        traffic = client.get("/__awatch/api/traffic?hours=24").json()
        assert "requests" in traffic
        assert "timeline" in traffic
        assert "endpoints" in traffic

        perf = client.get("/__awatch/api/performance?hours=24").json()
        assert "apdex" in perf
        assert "p95_ms" in perf

        errors = client.get("/__awatch/api/errors?hours=24").json()
        assert "status_codes" in errors
        assert "fingerprints" in errors

        uptime = client.get("/__awatch/api/uptime?hours=24").json()
        assert "config" in uptime
        assert uptime["config"]["enabled"] is False

        ping = client.get("/__awatch/api/uptime/ping").json()
        assert ping["ok"] is True

        saved = client.put(
            "/__awatch/api/config/performance",
            json={"apdex_t_ms": 250},
        )
        assert saved.status_code == 200
        assert saved.json()["apdex_t_ms"] == 250
