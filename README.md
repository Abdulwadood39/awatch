# monitorit (awatch)

**Self-hosted FastAPI monitoring** with a built-in dashboard — traffic, errors, Apdex, request logs, consumers, uptime, and alerts.

No Grafana. No cloud account. No phone-home telemetry. Metrics stay on your machine in SQLite.

**PyPI:** [`monitorit`](https://pypi.org/project/monitorit/) · **Import:** `from monitorit import awatch` · **Dashboard:** `/__awatch`

```python
from fastapi import FastAPI
from monitorit import awatch

app = FastAPI()
awatch.AWatch(app, env="dev")  # → http://127.0.0.1:8000/__awatch
```

A lightweight, privacy-first alternative to hosted API analytics (e.g. Apitally) and a simpler path than Prometheus + Grafana for single-app FastAPI services.

---

## Why monitorit?

| Need | monitorit |
|------|-----------|
| FastAPI request monitoring dashboard | Built-in at `/__awatch` |
| One-line setup | `awatch.AWatch(app)` |
| Self-hosted / on-prem | Local SQLite (default) |
| Request inspector | Opt-in headers, bodies, logs, cURL export |
| Consumer analytics | `awatch.set_consumer(...)` |
| Alerts | Email, Slack, Discord, webhook |
| Secret safety | Masking + path excludes by default |

---

## Install

**Python 3.10+** recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U pip
pip install monitorit
```

### From GitHub

```bash
pip install "git+https://github.com/Abdulwadood39/awatch.git"
```

### Editable / contributing

```bash
git clone https://github.com/Abdulwadood39/awatch.git
cd awatch
pip install -e ".[dev]"
```

### Verify

```bash
python -c "from monitorit import awatch; print(awatch.__version__, awatch.AWatch)"
```

Full details: [docs/installation.md](docs/installation.md).

---

## Quick start

1. Attach awatch to your FastAPI app (snippet above).
2. Run with uvicorn:

```bash
uvicorn your_module:app --reload
```

3. Open the **FastAPI monitoring dashboard**: [http://127.0.0.1:8000/__awatch](http://127.0.0.1:8000/__awatch).

### Try the demos in this repo

```bash
pip install -e ".[dev]"
uvicorn examples.basic_app:app --reload
```

```bash
curl http://127.0.0.1:8000/
curl -X POST http://127.0.0.1:8000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"gadget","price":9.5}'
curl http://127.0.0.1:8000/boom
```

### Production auth

`env="prod"` requires an `auth_token` (or `auth_dependency`):

```python
import os
from monitorit import awatch

awatch.AWatch(
    app,
    env="prod",
    auth_token=os.environ["AWATCH_TOKEN"],
    allow_ui_config=False,
)
```

Unlock the UI with `?token=...` or the in-browser Unlock dialog. More: [docs/usage.md](docs/usage.md).

---

## Features

- **Traffic / Errors / Performance** — per-endpoint stats, Apdex, timelines
- **Request inspector** — headers, bodies, correlated logs, exceptions, cURL export
- **Opt-in body/header logging** with default secret masking
- **Consumers** — `awatch.set_consumer()` for individuals and groups
- **Traffic labels** — categories defined in code
- **422 heatmaps** — which Pydantic fields fail validation
- **Do not track** — exclude sensitive paths (code or Settings)
- **Uptime** — heartbeat + synthetic checks + external ping
- **Alerts** — triggers in code → email / Slack / Discord / webhook
- **Settings UI** — SMTP, excludes, uptime, Apdex (lockable)
- **Auth gate** for production dashboards
- **Quiet access logs** — dashboard polls do not spam uvicorn (default on)
- **Retention controls** — age + row-cap prune (default 7 days / 10k rows)
- **Paginated request logs** — lightweight list payloads; full detail on click
- **Outbound HTTP inspector** — linked httpx calls under each inbound request
- **Postgres / MySQL** — optional storage backends (`monitorit[postgres|mysql]`)

---

## Documentation

| Doc | Topic |
|-----|--------|
| [docs/](docs/README.md) | Index |
| [Installation](docs/installation.md) | pip / venv / editable |
| [Usage](docs/usage.md) | Integrate & run |
| [Configuration](docs/configuration.md) | Options, Settings lock, excludes |
| [Dashboard](docs/dashboard.md) | Tabs & filters |
| [Consumers](docs/consumers.md) | `awatch.set_consumer()` |
| [Categories](docs/categories.md) | Traffic labels |
| [Alerts](docs/alerts.md) | Triggers |
| [Privacy](docs/privacy.md) | Masking & threat model |
| [Publishing](docs/publishing.md) | PyPI releases |

---

## Contributing

Contributions are welcome — bugs, docs, tests, dashboard UX, and features.

1. Open an [issue](https://github.com/Abdulwadood39/awatch/issues) for ideas or bugs
2. Fork, branch, and open a PR
3. Run `pytest` before submitting

Good first areas: documentation polish, more tests, Postgres storage, alert channels, dashboard UI.

---

## Development

```bash
pip install -e ".[dev]"
pytest
uvicorn examples.basic_app:app --reload
```

Package layout: `src/monitorit/awatch/` (`core`, `capture`, `privacy`, `analytics`, `storage`, `health`, `triggers`, `api`, `dashboard`).

---

## Links

- **GitHub:** https://github.com/Abdulwadood39/awatch
- **PyPI:** https://pypi.org/project/monitorit/
- **Issues:** https://github.com/Abdulwadood39/awatch/issues
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT © Abdulwadood
