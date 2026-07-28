# monitorit / awatch documentation

**Self-hosted FastAPI monitoring** with an embedded dashboard. Install **`monitorit`**, then `from monitorit import awatch`.

Data stays on your machine (SQLite by default). No Grafana stack and no cloud analytics account required.

| Guide | Description |
|-------|-------------|
| [Installation](installation.md) | Install into a Python env (pip / editable) |
| [Usage](usage.md) | Attach awatch, open the dashboard, generate traffic |
| [Configuration](configuration.md) | Auth, excludes, logging, Settings UI, storage |
| [Dashboard](dashboard.md) | Tabs, filters, path dropdowns |
| [Consumers](consumers.md) | Tag requests with `awatch.set_consumer()` |
| [Categories](categories.md) | Traffic labels (code-only) |
| [Alerts](alerts.md) | Triggers → email / Slack / Discord / webhook |
| [Privacy](privacy.md) | Masking, exclusions, threat model |
| [Publishing](publishing.md) | Release to PyPI (Trusted Publishing) |

Also see the [examples](../examples/), [CHANGELOG](../CHANGELOG.md), and the project [README](../README.md).

## Quick links

- PyPI: https://pypi.org/project/monitorit/
- GitHub: https://github.com/Abdulwadood39/awatch
- Dashboard path (default): `/__awatch`
