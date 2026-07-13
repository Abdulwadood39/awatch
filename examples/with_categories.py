"""Demo with categories."""

from fastapi import FastAPI, Request
from pydantic import BaseModel

from awatch import AWatch, CategoryRule, header_equals, path_prefix, set_consumer
import logging

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="awatch categories demo")

AWatch(
    app,
    env="prod",  # use env="prod" + auth_token="..." for protected dashboard
    db_path="./.awatch-categories.db",
    auth_token="secret",
    allow_ui_config=True,
    log_request_body=True,
    capture_logs=True,
    categories=[
        CategoryRule(name="admin", when=path_prefix("/admin"), priority=10),
        CategoryRule(name="partner", when=header_equals("X-Partner-Id", "*"), priority=5),
    ],
    release="1.0.0",
)


class Order(BaseModel):
    plan: str
    amount: float


@app.middleware("http")
async def identify(request: Request, call_next):
    user = request.headers.get("X-User", "anonymous")
    set_consumer(request, identifier=user, name=user, group="demo")
    return await call_next(request)


@app.get("/admin/stats")
def admin_stats():
    return {"admins": 1}


@app.post("/orders")
def create_order(order: Order):
    return order


@app.get("/health")
def health():
    logging.getLogger("demo").info("health check")
    return {"ok": True}
