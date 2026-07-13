"""Discord / Slack action unit smoke tests."""

from awatch.core.ui_config import compile_trigger_defs
from awatch.triggers.actions import DiscordNotify, SlackNotify
from awatch.triggers.events import TriggerEvent


def test_compile_discord_trigger():
    triggers = compile_trigger_defs(
        [
            {
                "name": "d1",
                "enabled": True,
                "cooldown": "5m",
                "when": {"status_from": 500, "status_to": 600, "path_pattern": "*"},
                "then": {
                    "type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/x/y",
                },
            }
        ]
    )
    assert len(triggers) == 1
    assert isinstance(triggers[0].then, DiscordNotify)
    assert triggers[0].cooldown == "5m"


def test_discord_payload_shape(monkeypatch):
    captured = {}

    class FakeResp:
        def read(self):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=10):
        captured["url"] = req.full_url
        captured["body"] = req.data
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    import asyncio

    action = DiscordNotify("https://discord.com/api/webhooks/x/y")
    event = TriggerEvent(
        kind="request",
        fingerprint="f",
        message="boom",
        details={"method": "GET", "path": "/x", "status_code": 500, "request_id": "abc"},
    )
    asyncio.run(action(event))
    assert b"content" in captured["body"]
    assert b"awatch" in captured["body"]


def test_slack_still_compiles():
    triggers = compile_trigger_defs(
        [
            {
                "name": "s1",
                "enabled": True,
                "when": {"status_from": 500, "status_to": 600, "path_pattern": "*"},
                "then": {"type": "slack", "webhook_url": "https://hooks.slack.com/x"},
            }
        ]
    )
    assert isinstance(triggers[0].then, SlackNotify)
