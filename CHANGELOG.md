# Changelog

## 0.1.0 — 2026-07-13

- Initial public release of **awatch** (A.W. Watch)
- One-line FastAPI integration with embedded dashboard at `/__awatch`
- Request metrics, request logs (opt-in), privacy masking, consumers, categories
- 422 validation heatmaps, OpenAPI inventory, health/ready probes
- Trigger engine with email, webhook, Slack, Discord, and log actions
- SQLite WAL storage with async single-writer queue
- Settings UI for SMTP, exclude paths, uptime, and Apdex (`allow_ui_config` lock)
- Modular dashboard assets (`dashboard/assets/css` + `js`)
- Path filter dropdowns from OpenAPI (`filterable_paths`, hides excludes + awatch routes)
- Consumers / categories / triggers are code-only (no Settings editors)
- Docs under [`docs/`](docs/README.md)
