# awatch

**A.W. Watch** — self-hosted FastAPI monitoring with a built-in dashboard. No Grafana, no cloud account. Data stays on your machine.

```python
from fastapi import FastAPI
from awatch import AWatch

app = FastAPI()
AWatch(app, env="dev")  # → http://127.0.0.1:8000/__awatch
```

---

## Install

**Python 3.10+** recommended. Use a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U pip
```

### From GitHub

```bash
pip install "git+https://github.com/Abdulwadood39/awatch.git"
```

### From a local clone (editable / contributing)

```bash
git clone https://github.com/Abdulwadood39/awatch.git
cd awatch
pip install -e ".[dev]"
```

### Verify

```bash
python -c "from awatch import AWatch; print('ok')"
```

Full details: [docs/installation.md](docs/installation.md).

---

## Usage

1. Attach awatch to your FastAPI app (see snippet above).
2. Run with uvicorn:

```bash
uvicorn your_module:app --reload
```

3. Open [http://127.0.0.1:8000/__awatch](http://127.0.0.1:8000/__awatch).

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
from awatch import AWatch

AWatch(
    app,
    env="prod",
    auth_token=os.environ["AWATCH_TOKEN"],
    allow_ui_config=False,
)
```

Unlock the UI with `?token=...` or the in-browser Unlock dialog. More: [docs/usage.md](docs/usage.md).

---

## Features

- **Traffic / Errors / Performance** — endpoints, Apdex, timelines
- **Request inspector** — headers, bodies, logs, exceptions, cURL export
- **Opt-in body/header logging** with default secret masking
- **Consumers** — `set_consumer()` for groups & individuals
- **Traffic labels** — categories in code
- **422 heatmaps** — which Pydantic fields fail validation
- **Do not track** — exclude sensitive paths (code or Settings)
- **Uptime** — heartbeat + synthetic checks + external ping
- **Alerts** — triggers in code → email / Slack / Discord / webhook
- **Settings UI** — SMTP, excludes, uptime, Apdex (lockable)
- **Auth gate** for production dashboards

---

## Documentation

| Doc | Topic |
|-----|--------|
| [docs/](docs/README.md) | Index |
| [Installation](docs/installation.md) | pip / venv / editable |
| [Usage](docs/usage.md) | Integrate & run |
| [Configuration](docs/configuration.md) | Options, Settings lock, excludes |
| [Dashboard](docs/dashboard.md) | Tabs & filters |
| [Consumers](docs/consumers.md) | `set_consumer()` |
| [Categories](docs/categories.md) | Traffic labels |
| [Alerts](docs/alerts.md) | Triggers |
| [Privacy](docs/privacy.md) | Masking & threat model |

---

## Development

```bash
pip install -e ".[dev]"
pytest
uvicorn examples.basic_app:app --reload
```

Package layout: `src/awatch/` (`core`, `capture`, `privacy`, `analytics`, `storage`, `health`, `triggers`, `api`, `dashboard`).

---

## License

MIT © Abdulwadood
