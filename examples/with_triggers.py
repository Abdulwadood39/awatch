"""Demo with triggers (5xx → log action; swap in SendEmail for real alerts)."""

import os

from fastapi import FastAPI

from awatch import AWatch, LogAction, Trigger
from awatch.triggers.conditions import path_matches, status_in
from awatch.triggers.actions import SendEmail

app = FastAPI(title="awatch triggers demo")

actions = [LogAction()]
if os.environ.get("AWATCH_SMTP_URL"):
    actions.append(
        SendEmail(
            to=[os.environ.get("AWATCH_ALERT_TO", "oncall@example.com")],
            subject="awatch: API 5xx",
        )
    )

AWatch(
    app,
    env="dev",
    db_path="./.awatch-triggers.db",
    triggers=[
        Trigger(
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
