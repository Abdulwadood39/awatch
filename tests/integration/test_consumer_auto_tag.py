"""Consumer tagging via set_consumer (code) — no UI fingerprint API."""

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from monitorit.awatch import AWatch, set_consumer


class Charge(BaseModel):
    company_id: str
    user_id: str
    plan: str
    amount: float


def test_set_consumer_tags_for_debugging(tmp_path: Path):
    app = FastAPI()

    @app.post("/payments/charge")
    def charge(request: Request, body: Charge):
        set_consumer(
            request,
            identifier=body.user_id,
            name=body.user_id,
            group=body.company_id,
        )
        return {"ok": True}

    AWatch(
        app,
        env="dev",
        db_path=str(tmp_path / "c.db"),
        allow_ui_config=False,
        log_request_body=True,
        uptime_enabled=False,
    )
    with TestClient(app) as client:
        r = client.post(
            "/payments/charge",
            json={
                "company_id": "acme",
                "user_id": "u42",
                "plan": "pro",
                "amount": 9.99,
            },
        )
        assert r.status_code == 200
        time.sleep(0.4)

        groups = client.get("/__awatch/api/consumers?view=groups&hours=24").json()
        assert any(g.get("group_name") == "acme" for g in groups["rows"])

        individuals = client.get(
            "/__awatch/api/consumers?view=individuals&group=acme&hours=24"
        ).json()
        assert any(c.get("consumer_id") == "u42" for c in individuals["rows"])
