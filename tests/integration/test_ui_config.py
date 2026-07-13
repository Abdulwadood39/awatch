"""UI config lock + CRUD tests (SMTP / excludes / performance)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from monitorit.awatch import AWatch


def test_config_locked_by_default(tmp_path: Path):
    app = FastAPI()
    AWatch(app, env="dev", db_path=str(tmp_path / "a.db"), allow_ui_config=False, uptime_enabled=False)
    with TestClient(app) as client:
        cfg = client.get("/__awatch/api/config").json()
        assert cfg["locked"] is True
        assert cfg["allow_ui_config"] is False
        denied = client.put(
            "/__awatch/api/config/smtp",
            json={"smtp_url": "smtp://localhost", "from_addr": "a@b", "default_to": []},
        )
        assert denied.status_code == 403
        # Removed Settings APIs
        assert client.put("/__awatch/api/config/categories", json=[]).status_code == 404
        assert client.put("/__awatch/api/config/triggers", json=[]).status_code == 404
        assert client.put("/__awatch/api/config/consumer-rules", json=[]).status_code == 404


def test_config_unlocked_can_save_smtp_and_excludes(tmp_path: Path):
    app = FastAPI()

    @app.get("/payments/charge")
    def charge():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    AWatch(app, env="dev", db_path=str(tmp_path / "b.db"), allow_ui_config=True, uptime_enabled=False)
    with TestClient(app) as client:
        openapi = client.get("/__awatch/api/openapi").json()
        assert openapi["path_count"] >= 1
        filterable = openapi["filterable_paths"]
        assert any(p["path"] == "/payments/charge" for p in filterable)
        assert not any(p["path"] == "/health" for p in filterable)
        assert not any(str(p["path"]).startswith("/__awatch") for p in filterable)

        smtp = client.put(
            "/__awatch/api/config/smtp",
            json={
                "smtp_url": "smtp://localhost:1025",
                "from_addr": "awatch@test",
                "default_to": ["ops@test"],
            },
        )
        assert smtp.status_code == 200

        excluded = client.put(
            "/__awatch/api/config/exclude-paths",
            json=[
                {"path": "/admin/stats", "enabled": True, "note": "sensitive admin"},
                {"path": "/private/*", "enabled": True},
            ],
        )
        assert excluded.status_code == 200
        active = excluded.json()["active_exclude_paths"]
        assert "/admin/stats" in active
        assert "/private/*" in active

        cfg = client.get("/__awatch/api/config").json()
        assert cfg["smtp"]["from_addr"] == "awatch@test"
        assert "categories" not in cfg
        assert "consumer_rules" not in cfg
        assert "triggers" not in cfg

        client.get("/admin/stats")
        import time

        time.sleep(0.3)
        rows = client.get("/__awatch/api/requests?path_contains=/admin/stats").json()
        assert rows == []
