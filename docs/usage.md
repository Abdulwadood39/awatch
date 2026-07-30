# Usage

Add a **FastAPI monitoring dashboard** in one line. monitorit (awatch) captures traffic, errors, and performance locally and serves the UI at `/__awatch`.

## Minimal integration

```python
from fastapi import FastAPI
from monitorit import awatch

app = FastAPI()
awatch.AWatch(app, env="dev")
```

```bash
uvicorn your_module:app --reload
```

Open [http://127.0.0.1:8000/__awatch](http://127.0.0.1:8000/__awatch).

## Demo apps in this repo

```bash
pip install -e ".[dev]"

uvicorn examples.basic_app:app --reload
uvicorn examples.with_categories:app --reload
uvicorn examples.with_triggers:app --reload
uvicorn examples.with_outbound:app --reload --port 8010
```

Generate traffic against the basic demo, then open **Request logs** and click a row:

```bash
curl http://127.0.0.1:8000/
curl -X POST http://127.0.0.1:8000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"gadget","price":9.5}'
curl http://127.0.0.1:8000/boom
```

## Choose a storage backend

Default is **SQLite** (one file, fine for single-process apps).

| Backend | Install | Config |
|---------|---------|--------|
| SQLite (default) | `pip install monitorit` | `db_path="./awatch.db"` |
| PostgreSQL | `pip install "monitorit[postgres]"` | `storage="postgres"`, `database_url="postgresql://…"` |
| MySQL | `pip install "monitorit[mysql]"` | `storage="mysql"`, `database_url="mysql://…"` |

```python
# SQLite (default)
awatch.AWatch(app, env="dev", db_path="./awatch.db")

# Postgres
awatch.AWatch(
    app,
    env="prod",
    auth_token="…",
    storage="postgres",
    database_url="postgresql://user:pass@localhost:5432/awatch",
)

# MySQL
awatch.AWatch(
    app,
    env="prod",
    auth_token="…",
    storage="mysql",
    database_url="mysql://user:pass@localhost:3306/awatch",
)
```

Prefer one writer process per database. Full option list: [Configuration](configuration.md).

## Retention (keep the DB bounded)

By default awatch prunes:

1. Rows older than `retention_hours` (default **168** = 7 days)
2. Oldest rows when over `max_requests` (default **10_000**)

```python
awatch.AWatch(
    app,
    env="dev",
    retention_hours=168,
    max_requests=10_000,
    prune_every=100,
    prune_on_startup=True,
)
```

Unlocked Settings → **Retention** can override these at runtime. Inbound and outbound rows both count toward the cap.

## Outbound HTTP (httpx)

When your FastAPI app calls other services with **httpx**, enable:

```python
awatch.AWatch(
    app,
    env="dev",
    instrument_outbound_http=True,
    log_request_body=True,   # optional
    log_response_body=True,  # optional
    max_outbound_per_request=50,
)
```

In **Request logs**, open an inbound request → use the **Outbound calls** dropdown to inspect each child call. Outbound rows count toward retention but are excluded from Traffic / Apdex endpoint charts.

Demo: `uvicorn examples.with_outbound:app --reload --port 8010`.

## Request inspector capture

Bodies and headers are **off by default** (privacy). Opt in when you need them:

```python
awatch.AWatch(
    app,
    env="dev",
    log_request_headers=True,
    log_request_body=True,
    log_response_headers=True,
    log_response_body=True,
    capture_logs=True,  # correlate stdlib logs on every request
)
```

**5xx / unhandled exceptions always store traceback + correlated logs**, even when `capture_logs=False`.

In the UI, Request logs support:

- Paginated list (summary rows only; full detail on click)
- Date separators + local-timezone times
- Copy buttons for request/response body and cURL
- Timing tab for SQL spans (when you wire `db_engine=…` / SQLAlchemy instrumentation)

## Tag who made the request (consumers)

```python
from fastapi import Depends, Request
from monitorit import awatch

@app.get("/items")
def items(request: Request, user=Depends(get_user)):
    awatch.set_consumer(
        request,
        identifier=user.id,
        name=user.email,
        group=user.company_id,
    )
    return []
```

See [Consumers](consumers.md).

## Traffic labels (categories)

Define labels in code with `categories=` on `AWatch`. There is no Settings UI for categories. See [Categories](categories.md).

## Alerts (triggers)

Triggers are **code-only**. Fired history shows under the **Alerts** tab.

```python
from monitorit import awatch
from monitorit.awatch.triggers.conditions import status_in, path_matches, error_rate_above
from monitorit.awatch.triggers.actions import SendEmail, SlackNotify

awatch.AWatch(
    app,
    env="prod",
    auth_token="…",
    triggers=[
        awatch.Trigger(
            name="payments_5xx",
            when=status_in(range(500, 600)) & path_matches("/payments/*"),
            then=SendEmail(
                to=["oncall@company.com"],
                subject="Payments API 5xx",
            ),
            cooldown="5m",
        ),
        awatch.Trigger(
            name="high_error_rate",
            when=error_rate_above(0.1, window="5m"),
            then=SlackNotify(webhook_url="https://hooks.slack.com/…"),
            cooldown="5m",
        ),
        awatch.Trigger(
            name="slow_p95",
            when=awatch.p95_above(1500, window="5m"),
            then=awatch.DiscordNotify(webhook_url="https://discord.com/api/webhooks/…"),
            cooldown="10m",
        ),
    ],
)
```

```bash
pip install "monitorit[slack]"   # Slack / Discord / webhook (httpx)
```

Configure SMTP for email actions in Settings (when unlocked) or via env / stored UI config.  
Demo: `uvicorn examples.with_triggers:app --reload`.

Full details: [Alerts](alerts.md).

## Production-shaped setup

```python
import os
from fastapi import FastAPI
from monitorit import awatch

app = FastAPI()

awatch.AWatch(
    app,
    env="prod",
    auth_token=os.environ["AWATCH_TOKEN"],
    allow_ui_config=False,  # hide Settings writes; Settings tab stays hidden in UI
    storage="postgres",
    database_url=os.environ["AWATCH_DATABASE_URL"],
    retention_hours=168,
    max_requests=50_000,
    instrument_outbound_http=True,
    quiet_access_logs=True,  # default on — dashboard polls won't spam uvicorn
)
```

`env="prod"` **requires** `auth_token` or `auth_dependency`.

### Unlock the dashboard in a browser

- Query param (saved in browser storage):  
  `http://127.0.0.1:8000/__awatch/?token=YOUR_TOKEN`
- Or open `/__awatch` and paste the token in the Unlock dialog

API clients:

```http
Authorization: Bearer YOUR_TOKEN
# or
X-AWatch-Token: YOUR_TOKEN
```

### Settings lock

| `allow_ui_config` | Effect |
|-------------------|--------|
| `False` (default) | Analytics visible; Settings tab **hidden**; Settings writes → **403** |
| `True` | Settings tab visible; edit SMTP, excludes, uptime, Apdex, retention |

Consumers, categories, and triggers stay **code-only** even when Settings is unlocked.

## Exclude sensitive paths

```python
awatch.AWatch(
    app,
    env="dev",
    exclude_paths=[
        "/auth/login",
        "/users/*/password",
        r"^/internal/.*$",
    ],
)
```

Or Settings → **Do not track** (needs `allow_ui_config=True`). See [Privacy](privacy.md) and [Configuration](configuration.md).

## Next

| Guide | Topic |
|-------|--------|
| [Configuration](configuration.md) | Full option table, retention, storage, outbound |
| [Dashboard](dashboard.md) | Tabs, filters, inspector |
| [Consumers](consumers.md) | `set_consumer()` |
| [Categories](categories.md) | Traffic labels |
| [Alerts](alerts.md) | Triggers & actions |
| [Privacy](privacy.md) | Masking & threat model |
