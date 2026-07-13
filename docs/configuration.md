# Configuration

Pass options to `AWatch(...)`. Categories, consumers, and triggers are **code-only**. The Settings UI (when unlocked) edits SMTP, exclude paths, uptime, and Apdex.

## Common options

| Option | Default | Notes |
|--------|---------|-------|
| `env` | `"dev"` | `"prod"` requires auth |
| `dashboard_path` | `"/__awatch"` | Mount path for UI + APIs |
| `db_path` | `"./awatch.db"` | SQLite file |
| `auth_token` | `None` | Shared secret for dashboard/API |
| `auth_dependency` | `None` | Custom FastAPI dependency instead of token |
| `allow_ui_config` | `False` | Unlock Settings writes |
| `exclude_paths` | `[]` | Extra “do not track” patterns (merged with defaults) |
| `log_request_headers` / `log_request_body` | `False` | Opt-in capture |
| `log_response_headers` / `log_response_body` | `False` | Opt-in capture |
| `capture_logs` | `False` | Correlate stdlib logs on every request |
| `success_sample_rate` | `1.0` | Sample successful requests |
| `slow_threshold_ms` | `1000` | Slow-request highlighting |
| `max_requests` | `10000` | Cap retained request rows |
| `retention_hours` | `168` | Auto-prune age |
| `categories` | `None` | Code-defined traffic labels |
| `triggers` | `None` | Code-defined alerts |
| `apdex_t_ms` | (config) | Apdex threshold |
| `uptime_enabled` / `uptime_path` / `uptime_interval_seconds` | on / `/health` / `60` | Synthetic checks |

## Lock / unlock Settings

| Setting | Effect |
|---------|--------|
| `allow_ui_config=False` (default) | Analytics visible; Settings writes → **403** |
| `allow_ui_config=True` | Admins can edit SMTP, excludes, uptime, Apdex |

Unlocked Settings does **not** configure consumers, categories, or triggers.

## Exclude sensitive APIs

Excluded routes skip metrics, bodies, and logs entirely.

```python
AWatch(
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
AWatch(
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
watch = AWatch(app, env="dev")
watch.register_probe("db", my_db_ping)
```

## Storage

Default: **SQLite WAL** at `./awatch.db`. Prefer one writer process per DB file.
