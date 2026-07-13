"""Dashboard API smoke."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from monitorit.awatch import AWatch


def test_openapi_drift_endpoint(tmp_path: Path):
    app = FastAPI()

    @app.get("/only-registered")
    def only():
        return {"ok": True}

    AWatch(app, env="dev", db_path=str(tmp_path / "d.db"))
    with TestClient(app) as client:
        client.get("/only-registered")
        import time

        time.sleep(0.3)
        drift = client.get("/__awatch/api/openapi-drift").json()
        assert "registered" in drift
        assert "dead" in drift
        assert "undocumented" in drift
