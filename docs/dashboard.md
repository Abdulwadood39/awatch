# Dashboard

URL: `{dashboard_path}` (default `/__awatch`).

## Tabs

| Tab | What you see |
|-----|----------------|
| Traffic | Request volume, status mix, endpoints |
| Errors | Status codes, exception fingerprints, 422 heatmap |
| Performance | Latency / Apdex |
| Consumers | Groups \| Individuals, adoption |
| Request logs | Filterable inspector (headers, bodies, logs, cURL) |
| Uptime | Heartbeat + synthetic checks |
| Alerts | Fired trigger history (configure triggers in code) |
| Settings | SMTP, excludes, uptime, Apdex (when unlocked) |

## Filters

- Time range (hours) applies across analytics tabs
- Global consumer / group chips narrow Traffic, Errors, Performance, and logs
- **Request logs → path**: dropdown of filterable OpenAPI paths (excludes “do not track” routes and awatch dashboard routes), plus a free-text “path contains” field
- Clicking Traffic / Errors / Performance rows can jump to Request logs with path/status prefilled

## Modular UI assets

The UI is split under `src/awatch/dashboard/`:

```
dashboard/
├── index.html
└── assets/
    ├── css/dashboard.css
    └── js/  core · charts · panels · settings · app
```

Static files are served at `{dashboard_path}/assets`.
