# Changelog

## 0.1.3 — 2026-07-29

- Improve GitHub / PyPI documentation for discoverability (FastAPI monitoring positioning, features table, contributing)
- Expand package description and keywords on PyPI

## 0.1.2 — 2026-07-29

- Quiet uvicorn access logs for dashboard polls and health probes by default (`quiet_access_logs=True`)
- Slow dashboard auto-refresh to 30s and pause while the browser tab is hidden
- Add `monitorit.awatch.capture.access_log.install_quiet_access_logs` helper

## 0.1.1 — 2026-07-29

- Publish workflow / tagging follow-up (no package feature changes)

## 0.1.0 — 2026-07-13

- Initial public release: PyPI name **`monitorit`**, module **`from monitorit import awatch`**
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
