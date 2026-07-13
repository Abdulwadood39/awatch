"""DB / callback category loaders."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from monitorit.awatch.analytics.categories.rules import (
    CategoryRule,
    header_equals,
    json_path_equals,
    path_matches,
    path_prefix,
    query_equals,
)


def _build_rule(name: str, rule_type: str, rule_value: str, priority: int = 0) -> CategoryRule:
    rt = rule_type.lower()
    if rt == "path_prefix":
        when = path_prefix(rule_value)
    elif rt == "path_matches":
        when = path_matches(rule_value)
    elif rt.startswith("header:"):
        header = rt.split(":", 1)[1]
        when = header_equals(header, rule_value)
    elif rt.startswith("query:"):
        q = rt.split(":", 1)[1]
        when = query_equals(q, rule_value)
    elif rt.startswith("json:"):
        path = rt.split(":", 1)[1]
        when = json_path_equals(path, rule_value)
    else:
        when = path_prefix(rule_value)
    return CategoryRule(name=name, when=when, priority=priority)


def callback_loader(fn: Callable[[], Iterable[dict[str, Any]]]) -> Callable[[], list[CategoryRule]]:
    def _load() -> list[CategoryRule]:
        rows = list(fn())
        return [
            _build_rule(
                r["name"],
                r.get("rule_type", "path_prefix"),
                r.get("rule_value", ""),
                int(r.get("priority", 0)),
            )
            for r in rows
        ]

    return _load


def sqlalchemy_loader(engine: Any, sql: str) -> Callable[[], list[CategoryRule]]:
    """Load rules from SQL returning name, rule_type, rule_value, priority."""

    def _load() -> list[CategoryRule]:
        from sqlalchemy import text

        with engine.connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()
        return [
            _build_rule(
                row["name"],
                row.get("rule_type", "path_prefix"),
                row.get("rule_value", ""),
                int(row.get("priority", 0)),
            )
            for row in rows
        ]

    return _load
