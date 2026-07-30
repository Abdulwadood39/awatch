# Dashboard

URL: `{dashboard_path}` (default `/__awatch`).

Times in the UI are shown in your **browser’s local timezone** (data is stored in UTC).

## Tabs

| Tab | What you see |
|-----|----------------|
| Traffic | Volume cards, **hourly** timeline (adaptive grain), endpoint table |
| Errors | Status codes, exception fingerprints, 422 heatmap, error timeline |
| Performance | Latency / Apdex by endpoint |
| Consumers | Groups \| Individuals, adoption stats |
| Request logs | Paginated list + inspector (headers, bodies, logs, cURL, outbound) |
| Uptime | Heartbeat + synthetic checks timeline |
| Alerts | Fired trigger history (configure triggers in **code**) |
| Settings | SMTP, excludes, uptime, Apdex, retention — **only when unlocked** |

When `allow_ui_config=False`, the **Settings** tab is hidden.

## Traffic timeline

- Window **≤ 1h** → per-minute bars  
- Window **≤ 48h** (including 24h) → **per-hour** bars with empty hours filled in  
- Longer windows → per-day bars  

Each bar is stacked: **blue = success**, **red = failed (4xx/5xx)**. Hover for total / success / failed.

## Request logs

- Lightweight **paginated** list (no bodies in the list payload)
- Click a row for full detail
- **Date separators** (`30-7-26`) when the local day changes; rows show time only
- **Outbound calls** dropdown when `instrument_outbound_http=True`
- **Copy** on request/response body, cURL, and exceptions
- **Timing** tab lists SQL/dependency spans (when SQLAlchemy instrumentation is wired)

## Filters

- Time range (1h / 24h / 7d / 30d) applies across analytics tabs
- Global consumer / group chips narrow Traffic, Errors, Performance, and logs
- **Request logs → path**: OpenAPI path dropdown + free-text “path contains”
- **Reset filters** appears when any request-log filter is active
- Clicking Traffic / Errors / Performance rows can jump to Request logs with path/status prefilled

## Mobile

- Top brand bar + hamburger opens pill-style nav (wraps; no page horizontal scroll)
- Request list and inspector stack; tables stay contained

## Modular UI assets

```
dashboard/
├── index.html
└── assets/
    ├── css/dashboard.css
    └── js/  core · charts · panels · settings · app
```

Static files are served at `{dashboard_path}/assets`.
