"""Demo with triggers (5xx → log action; swap in SendEmail for real alerts)."""

import os

from fastapi import FastAPI

from monitorit import awatch
from monitorit.awatch.triggers.conditions import path_matches, status_in
from monitorit.awatch.triggers.actions import SendEmail

app = FastAPI(title="awatch triggers demo")

actions = [awatch.LogAction()]
if os.environ.get("AWATCH_SMTP_URL"):
    actions.append(
        SendEmail(
            to=[os.environ.get("AWATCH_ALERT_TO", "oncall@example.com")],
            subject="awatch: API 5xx",
        )
    )

awatch.AWatch(
    app,
    env="dev",
    db_path="./.awatch-triggers.db",
    triggers=[
        awatch.Trigger(
            name="page_on_5xx",
            when=status_in(range(500, 600)) & path_matches("/payments/*"),
            then=actions,
            cooldown="1m",
        ),
    ],
)


@app.get("/payments/charge")
def charge():
    raise RuntimeError("payment processor down")


@app.get("/ok")
def ok():
    return {"ok": True}
