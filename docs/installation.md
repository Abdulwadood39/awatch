# Installation

Requires **Python 3.10+** and a FastAPI app.

## Install into a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -U pip
pip install awatch
```

If the package is not on PyPI yet, install from GitHub:

```bash
pip install "git+https://github.com/Abdulwadood39/awatch.git"
```

Or a specific tag/branch:

```bash
pip install "git+https://github.com/Abdulwadood39/awatch.git@main"
```

## Install from a local clone (development)

```bash
git clone https://github.com/Abdulwadood39/awatch.git
cd awatch

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

`.[dev]` pulls pytest, uvicorn, httpx, and ruff for local demos and tests.

## Optional extras

| Extra | Install | Purpose |
|-------|---------|---------|
| `dev` | `pip install "awatch[dev]"` | Tests + local server |
| `slack` | `pip install "awatch[slack]"` | Slack / Discord / webhook HTTP client (`httpx`) |
| `postgres` | `pip install "awatch[postgres]"` | Future Postgres storage driver |

## Verify

```bash
python -c "from awatch import AWatch; print('awatch OK')"
```

Next: [Usage](usage.md).
