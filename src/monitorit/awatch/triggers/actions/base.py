"""Action protocol and built-ins."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Protocol
from urllib.parse import urlparse

logger = logging.getLogger("awatch.triggers")


class Action(Protocol):
    async def __call__(self, event: Any) -> None: ...


class LogAction:
    async def __call__(self, event: Any) -> None:
        logger.warning("awatch trigger: %s — %s", event.kind, event.message)


class SendEmail:
    def __init__(
        self,
        to: list[str],
        subject: str,
        smtp_url: str | None = None,
        from_addr: str | None = None,
    ) -> None:
        self.to = to
        self.subject = subject
        self.smtp_url = smtp_url
        self.from_addr = from_addr or "awatch@localhost"

    async def __call__(self, event: Any) -> None:
        import os

        smtp_url = self.smtp_url or os.environ.get("AWATCH_SMTP_URL")
        if not smtp_url:
            logger.warning("SendEmail skipped: no smtp_url / AWATCH_SMTP_URL")
            return
        parsed = urlparse(smtp_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 587
        user = parsed.username
        password = parsed.password

        msg = EmailMessage()
        msg["Subject"] = self.subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to)
        msg.set_content(f"{event.message}\n\nDetails: {event.details}")

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            try:
                smtp.starttls()
            except Exception:  # noqa: BLE001
                pass
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)


class Webhook:
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}

    async def __call__(self, event: Any) -> None:
        import json
        from urllib.request import Request, urlopen

        payload = json.dumps(
            {"kind": event.kind, "message": event.message, "details": event.details}
        ).encode()
        req = Request(self.url, data=payload, headers=self.headers, method="POST")
        with urlopen(req, timeout=10) as resp:  # noqa: S310 — user-configured webhook
            resp.read()


class SlackNotify:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def __call__(self, event: Any) -> None:
        import json
        from urllib.request import Request, urlopen

        payload = json.dumps({"text": f"*awatch* {event.message}"}).encode()
        req = Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            resp.read()


class DiscordNotify:
    """Send an alert to a Discord incoming webhook URL."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def __call__(self, event: Any) -> None:
        import json
        from urllib.request import Request, urlopen

        # Discord webhooks expect {"content": "..."} (max 2000 chars)
        content = f"**awatch** {event.message}"
        details = event.details or {}
        extras = []
        if details.get("path"):
            extras.append(f"`{details.get('method', '')} {details.get('path')}`")
        if details.get("status_code") is not None:
            extras.append(f"status `{details['status_code']}`")
        if details.get("request_id"):
            extras.append(f"id `{details['request_id']}`")
        if extras:
            content = f"{content}\n" + " · ".join(extras)
        content = content[:2000]

        payload = json.dumps({"content": content}).encode()
        req = Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            resp.read()
