# Alerts (triggers)

Define triggers in code. Fired history appears under **Alerts** in the dashboard.

```python
from monitorit import awatch
from monitorit.awatch.triggers.conditions import status_in, path_matches, error_rate_above
from monitorit.awatch.triggers.actions import SendEmail, SlackNotify, Webhook

awatch.AWatch(
    app,
    env="prod",
    auth_token="...",
    triggers=[
        awatch.Trigger(
            name="payments_5xx",
            when=status_in(range(500, 600)) & path_matches("/payments/*"),
            then=SendEmail(
                to=["oncall@company.com"],
                subject="Payments API 5xx",
            ),
            cooldown="5m",
        ),
        awatch.Trigger(
            name="high_error_rate",
            when=error_rate_above(0.1, window="5m"),
            then=SlackNotify(webhook_url="https://hooks.slack.com/..."),
            cooldown="5m",
        ),
        awatch.Trigger(
            name="slow_p95",
            when=awatch.p95_above(1500, window="5m"),
            then=awatch.DiscordNotify(webhook_url="https://discord.com/api/webhooks/..."),
            cooldown="10m",
        ),
    ],
)
```

Install `httpx` for Slack / Discord / webhook actions:

```bash
pip install "monitorit[slack]"
```

Configure SMTP for email actions in Settings (unlocked) or via stored UI config.

Demo:

```bash
uvicorn examples.with_triggers:app --reload
```

There is **no** Settings UI to create triggers — pass `triggers=` on `awatch.AWatch(...)`.
