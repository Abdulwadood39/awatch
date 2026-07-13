"""awatch — A.W. Watch: self-hosted FastAPI monitoring."""

from monitorit.awatch.analytics.categories import (
    CategoryRule,
    callback_loader,
    header_equals,
    json_path_equals,
    path_matches,
    path_prefix,
    sqlalchemy_loader,
)
from monitorit.awatch.analytics.consumers import set_consumer
from monitorit.awatch.core.app import AWatch
from monitorit.awatch.triggers import (
    DiscordNotify,
    LogAction,
    SendEmail,
    SlackNotify,
    Trigger,
    Webhook,
    apdex_below,
    category_is,
    duration_above,
    error_rate_above,
    p95_above,
    rpm_above,
    status_in,
)
from monitorit.awatch.triggers.conditions import path_matches as trigger_path_matches

__all__ = [
    "AWatch",
    "set_consumer",
    "CategoryRule",
    "header_equals",
    "json_path_equals",
    "path_prefix",
    "path_matches",
    "callback_loader",
    "sqlalchemy_loader",
    "Trigger",
    "status_in",
    "trigger_path_matches",
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

__version__ = "0.1.0"
