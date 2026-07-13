"""Triggers package."""

from awatch.triggers.conditions import (
    apdex_below,
    category_is,
    duration_above,
    error_rate_above,
    p95_above,
    path_matches,
    rpm_above,
    status_in,
)
from awatch.triggers.engine import TriggerEngine
from awatch.triggers.rules import Trigger
from awatch.triggers.actions import DiscordNotify, LogAction, SendEmail, SlackNotify, Webhook

__all__ = [
    "Trigger",
    "TriggerEngine",
    "status_in",
    "path_matches",
    "error_rate_above",
    "duration_above",
    "category_is",
    "rpm_above",
    "p95_above",
    "apdex_below",
    "SendEmail",
    "Webhook",
    "SlackNotify",
    "DiscordNotify",
    "LogAction",
]
