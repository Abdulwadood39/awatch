# Privacy & threat model

- Aggregated metrics are always on (method, route, status, latency, sizes)
- Headers / bodies / logs are **opt-in**
- Default masks for `Authorization`, cookies, tokens, passwords, and similar fields
- Sensitive routes can be fully excluded (`exclude_paths` or Settings → Do not track)
- Production dashboard requires auth; browser shows a token unlock form
- Settings mutations require `allow_ui_config=True`
- No phone-home telemetry
- No request replay (SSRF risk); cURL export only
- Data residency: local `awatch.db` under your control

Custom masks:

```python
AWatch(
    app,
    env="prod",
    auth_token="...",
    mask_headers=["X-Api-Key", "Cookie"],
    mask_query_params=["token"],
    mask_body_fields=["password", "ssn", "card_number"],
)
```
