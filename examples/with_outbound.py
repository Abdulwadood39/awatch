"""Demo: inbound + outbound httpx calls in the Request inspector.

Run:
  uvicorn examples.with_outbound:app --reload --port 8010

Then open http://127.0.0.1:8010/__awatch → Request logs.
Click a /checkout-tagged row and use the Outbound calls dropdown.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel

from monitorit import awatch
from monitorit.awatch.analytics.consumers import set_consumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound_demo")

app = FastAPI(title="awatch outbound demo")
awatch.AWatch(
    app,
    env="dev",
    db_path="./.awatch-outbound-demo.db",
    allow_ui_config=False,
    instrument_outbound_http=True,
    retention_hours=168,
    max_requests=10_000,
    prune_every=100,
    prune_on_startup=True,
    log_request_headers=True,
    log_request_body=True,
    log_response_headers=True,
    log_response_body=True,
    capture_logs=True,
    uptime_enabled=False,
)


class Checkout(BaseModel):
    order_id: str
    amount: float


@app.get("/")
def root():
    return {
        "ok": True,
        "dashboard": "http://127.0.0.1:8010/__awatch",
        "try": ["POST /checkout-tagged", "GET /items/1", "GET /boom"],
    }


@app.get("/items/{item_id}")
def get_item(item_id: int):
    logger.info("fetching item %s", item_id)
    return {"id": item_id, "name": "widget"}


@app.get("/internal/payments/charge")
def charge(order_id: str, amount: float):
    """Simulates a PHP/payment backend HostBNB would call."""
    logger.info("charging order=%s amount=%s", order_id, amount)
    return {"charged": True, "order_id": order_id, "amount": amount, "ref": "pay_demo_1"}


@app.get("/internal/notify")
def notify(order_id: str):
    logger.info("notify managers for %s", order_id)
    return {"notified": True, "channel": "manager", "order_id": order_id}


@app.post("/checkout-tagged")
async def checkout_tagged(body: Checkout, request: Request):
    """Inbound API that makes two outbound httpx calls (like HostBNB → PHP)."""
    set_consumer(
        request,
        identifier=body.order_id,
        name=f"Order {body.order_id}",
        group="demo-store",
    )
    base = "http://127.0.0.1:8010"
    async with httpx.AsyncClient(timeout=10.0) as client:
        pay = await client.get(
            f"{base}/internal/payments/charge",
            params={"order_id": body.order_id, "amount": body.amount},
        )
        note = await client.get(
            f"{base}/internal/notify",
            params={"order_id": body.order_id},
        )
    return {
        "ok": True,
        "order_id": body.order_id,
        "payment": pay.json(),
        "notify": note.json(),
    }


@app.get("/boom")
def boom():
    raise RuntimeError("intentional failure")

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("examples.with_outbound:app", host="127.0.0.1", port=8010, reload=True)
