"""Minimal FastAPI app with awatch."""

import logging

from fastapi import FastAPI
from pydantic import BaseModel

from awatch import AWatch

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="awatch demo")
AWatch(
    app,
    env="dev",
    db_path="./.awatch-demo.db",
    allow_ui_config=True,
    # Capture full request context for the inspector UI (opt-in; off by default in prod)
    log_request_headers=True,
    log_request_body=True,
    log_response_headers=True,
    log_response_body=True,
    capture_logs=True,
)


class Item(BaseModel):
    name: str
    price: float


@app.get("/")
def root():
    return {"ok": True}


@app.get("/items/{item_id}")
def get_item(item_id: int):
    import logging

    logging.getLogger("demo").info("fetching item %s", item_id)
    return {"id": item_id, "name": "widget"}


@app.post("/items")
def create_item(item: Item):
    import logging

    logging.getLogger("demo").info("creating item name=%s price=%s", item.name, item.price)
    return item


@app.get("/boom")
def boom():
    import logging

    logging.getLogger("demo").error("about to fail intentionally")
    raise RuntimeError("intentional failure")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
