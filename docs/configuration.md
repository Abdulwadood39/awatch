# Configuration

Pass options to `awatch.AWatch(...)`. Categories, consumers, and triggers are **code-only**. The Settings UI (when unlocked) edits SMTP, exclude paths, uptime, Apdex, and retention.

## Common options

| Option | Default | Notes |
|--------|---------|-------|
| `env` | `"dev"` | `"prod"` requires auth |
| `dashboard_path` | `"/__awatch"` | Mount path for UI + APIs |
| `storage` | `"sqlite"` | `"sqlite"` \| `"postgres"` \| `"mysql"` |
| `db_path` | `"./awatch.db"` | SQLite file |
| `database_url` | `None` | Required for postgres/mysql |
| `auth_token` | `None` | Shared secret for dashboard/API |
| `auth_dependency` | `None` | Custom FastAPI dependency instead of token |
| `allow_ui_config` | `False` | Unlock Settings writes |
| `exclude_paths` | `[]` | Extra “do not track” patterns (merged with defaults) |
| `log_request_headers` / `log_request_body` | `False` | Opt-in capture |
| `log_response_headers` / `log_response_body` | `False` | Opt-in capture |
| `capture_logs` | `False` | Correlate stdlib logs on every request |
| `success_sample_rate` | `1.0` | Sample successful requests |
| `slow_threshold_ms` | `1000` | Slow-request highlighting |
| `max_requests` | `10000` | Cap retained request rows (inbound + outbound) |
| `retention_hours` | `168` | Auto-prune age (7 days) |
| `prune_every` | `100` | Run prune after every N writes |
| `prune_on_startup` | `True` | Prune once on app startup |
| `max_outbound_per_request` | `50` | Cap outbound children per parent |
| `instrument_outbound_http` | `False` | Record httpx outbound calls as linked requests |
| `categories` | `None` | Code-defined traffic labels |
| `triggers` | `None` | Code-defined alerts |
| `apdex_t_ms` | (config) | Apdex threshold |
| `uptime_enabled` / `uptime_path` / `uptime_interval_seconds` | on / `/health` / `60` | Synthetic checks |

## Retention (DB will not grow forever)

After each `prune_every` writes (and optionally on startup), awatch:

1. Deletes rows older than `retention_hours` (default **7 days**)
2. If still over `max_requests`, deletes the **oldest** rows until under the cap

```python
awatch.AWatch(
    app,
    retention_hours=168,
    max_requests=10_000,
    prune_every=100,
    prune_on_startup=True,
)
```

Unlocked Settings → **Retention** can override these at runtime.

## Outbound HTTP (e.g. PHP backend calls)

```python
awatch.AWatch(
    app,
    instrument_outbound_http=True,  # patches httpx AsyncClient + Client
    log_request_body=True,          # optional: capture outbound bodies too
    log_response_body=True,
)
```

Outbound calls appear in the Request inspector **Outbound calls** dropdown, linked to the parent inbound request. They count toward retention caps but are excluded from traffic/Apdex endpoint charts.

## Storage backends

```bash
pip install monitorit[postgres]   # or monitorit[mysql]
```

```python
awatch.AWatch(
    app,
    storage="postgres",  # or "mysql"
    database_url="postgresql://user:pass@localhost:5432/awatch",
)
```

## Lock / unlock Settings

| Setting | Effect |
|---------|--------|
| `allow_ui_config=False` (default) | Analytics visible; Settings tab **hidden**; Settings writes → **403** |
| `allow_ui_config=True` | Settings tab visible; admins can edit SMTP, excludes, uptime, Apdex, retention |

Unlocked Settings does **not** configure consumers, categories, or triggers. When locked, the Settings tab is hidden in the dashboard.

## Exclude sensitive APIs

Excluded routes skip metrics, bodies, and logs entirely.

```python
from monitorit import awatch

awatch.AWatch(
    app,
    env="dev",
    exclude_paths=[
        "/auth/login",
        "/users/*/password",   # glob
        r"^/internal/.*$",     # regex
    ],
)
```

Or: Settings → **Do not track** (needs `allow_ui_config=True`). The path dropdown uses OpenAPI routes minus active excludes and awatch dashboard paths.

Built-in defaults already skip `/health`, `/docs`, `/redoc`, `/openapi.json`, `/metrics`, and the dashboard path.

## Request inspector capture

```python
from monitorit import awatch

awatch.AWatch(
    app,
    env="dev",
    log_request_headers=True,
    log_request_body=True,
    log_response_headers=True,
    log_response_body=True,
    capture_logs=True,
)
```

**5xx and unhandled exceptions always store correlated logs + traceback**, even when `capture_logs=False`.

## Health probes

| Path | Purpose |
|------|---------|
| `{dashboard_path}` | Dashboard UI |
| `{dashboard_path}/health` | Liveness |
| `{dashboard_path}/ready` | Readiness |

```python
from monitorit import awatch

watch = awatch.AWatch(app, env="dev")
watch.register_probe("db", my_db_ping)
```

## Storage

| Backend | Extra | Notes |
|---------|-------|-------|
| SQLite (default) | — | WAL file at `db_path` (default `./awatch.db`) |
| PostgreSQL | `monitorit[postgres]` | `storage="postgres"` + `database_url` |
| MySQL | `monitorit[mysql]` | `storage="mysql"` + `database_url` |

Prefer one writer process per database. See [Usage](usage.md#choose-a-storage-backend).
