"""Analytics package."""

from awatch.analytics.consumers import set_consumer
from awatch.analytics.categories import (
    CategoryEngine,
    CategoryRule,
    callback_loader,
    header_equals,
    json_path_equals,
    path_matches,
    path_prefix,
    sqlalchemy_loader,
)

__all__ = [
    "set_consumer",
    "CategoryEngine",
    "CategoryRule",
    "callback_loader",
    "sqlalchemy_loader",
    "header_equals",
    "json_path_equals",
    "path_matches",
    "path_prefix",
]
