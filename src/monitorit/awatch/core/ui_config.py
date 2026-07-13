"""Compile UI-stored category/trigger definitions into runtime objects."""

from __future__ import annotations

from typing import Any

from monitorit.awatch.analytics.consumer_rules import compile_consumer_defs
from monitorit.awatch.analytics.categories.loaders import _build_rule
from monitorit.awatch.analytics.categories.rules import CategoryRule
from monitorit.awatch.triggers.actions import DiscordNotify, LogAction, SendEmail, SlackNotify, Webhook
from monitorit.awatch.triggers.conditions import (
    apdex_below,
    error_rate_above,
    p95_above,
    path_matches,
    rpm_above,
    status_in,
)
from monitorit.awatch.triggers.rules import Trigger

__all__ = [
    "compile_category_defs",
    "compile_trigger_defs",
    "compile_consumer_defs",
    "parse_openapi_paths",
    "aggregate_openapi_keys",
]


def compile_category_defs(defs: list[dict[str, Any]]) -> list[CategoryRule]:
    rules: list[CategoryRule] = []
    for d in defs:
        if not d.get("enabled", True):
            continue
        rules.append(
            _build_rule(
                name=str(d["name"]),
                rule_type=str(d.get("rule_type", "path_prefix")),
                rule_value=str(d.get("rule_value", "")),
                priority=int(d.get("priority", 0)),
            )
        )
    return rules


def compile_trigger_defs(
    defs: list[dict[str, Any]],
    *,
    smtp: dict[str, Any] | None = None,
) -> list[Trigger]:
    smtp = smtp or {}
    triggers: list[Trigger] = []
    for d in defs:
        if not d.get("enabled", True):
            continue
        when_cfg = d.get("when") or {}
        metric = str(when_cfg.get("metric") or "status").lower()
        pattern = when_cfg.get("path_pattern") or "*"
        window = str(when_cfg.get("window") or "5m")

        if metric == "error_rate":
            rate = float(when_cfg.get("threshold", 0.1))
            cond = error_rate_above(rate, window=window) & path_matches(pattern)
        elif metric == "rpm":
            cond = rpm_above(float(when_cfg.get("threshold", 100)), window=window) & path_matches(
                pattern
            )
        elif metric == "p95":
            cond = p95_above(float(when_cfg.get("threshold", 1000)), window=window) & path_matches(
                pattern
            )
        elif metric == "apdex":
            cond = apdex_below(
                float(when_cfg.get("threshold", 0.7)),
                t_ms=float(when_cfg.get("apdex_t_ms", 500)),
                window=window,
            ) & path_matches(pattern)
        else:
            status_from = int(when_cfg.get("status_from", 500))
            status_to = int(when_cfg.get("status_to", 600))
            cond = status_in(range(status_from, status_to)) & path_matches(pattern)

        then_cfg = d.get("then") or {}
        action_type = str(then_cfg.get("type", "log")).lower()
        action: Any
        if action_type == "email":
            action = SendEmail(
                to=list(then_cfg.get("to") or smtp.get("default_to") or []),
                subject=str(then_cfg.get("subject") or f"awatch: {d.get('name')}"),
                smtp_url=then_cfg.get("smtp_url") or smtp.get("smtp_url"),
                from_addr=then_cfg.get("from_addr") or smtp.get("from_addr"),
            )
        elif action_type == "slack":
            action = SlackNotify(webhook_url=str(then_cfg.get("webhook_url") or ""))
        elif action_type == "discord":
            action = DiscordNotify(webhook_url=str(then_cfg.get("webhook_url") or ""))
        elif action_type == "webhook":
            action = Webhook(url=str(then_cfg.get("url") or then_cfg.get("webhook_url") or ""))
        else:
            action = LogAction()

        triggers.append(
            Trigger(
                name=str(d["name"]),
                when=cond,
                then=action,
                cooldown=str(d.get("cooldown") or "5m"),
            )
        )
    return triggers


def _resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if ref and isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.split("/")[-1]
        return dict((components.get("schemas") or {}).get(name) or {})
    return schema


def _body_fields(schema: dict[str, Any], components: dict[str, Any], prefix: str = "") -> list[str]:
    schema = _resolve_schema(schema, components)
    fields: list[str] = []
    props = schema.get("properties") or {}
    if isinstance(props, dict):
        for key, sub in props.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            fields.append(path)
            if isinstance(sub, dict):
                nested = _resolve_schema(sub, components)
                if nested.get("type") == "object" or nested.get("properties") or nested.get("$ref"):
                    fields.extend(_body_fields(nested, components, path))
    return fields


def parse_openapi_paths(openapi: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten OpenAPI paths into selectable endpoint rows with parameter/body keys."""
    paths = openapi.get("paths") or {}
    components = openapi.get("components") or {}
    rows: list[dict[str, Any]] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        shared_params = methods.get("parameters") if isinstance(methods.get("parameters"), list) else []
        for method, meta in methods.items():
            if method.lower() in {"parameters", "summary", "description", "servers"}:
                continue
            if not isinstance(meta, dict):
                continue

            headers: list[str] = []
            query: list[str] = []
            path_params: list[str] = []
            params = list(shared_params) + list(meta.get("parameters") or [])
            for param in params:
                if not isinstance(param, dict):
                    continue
                name = param.get("name")
                loc = (param.get("in") or "").lower()
                if not name:
                    continue
                if loc == "header":
                    headers.append(str(name))
                elif loc == "query":
                    query.append(str(name))
                elif loc == "path":
                    path_params.append(str(name))

            body_fields: list[str] = []
            request_body = meta.get("requestBody") or {}
            content = request_body.get("content") if isinstance(request_body, dict) else {}
            if isinstance(content, dict):
                for ctype, media in content.items():
                    if "json" not in str(ctype).lower():
                        continue
                    if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                        body_fields.extend(_body_fields(media["schema"], components))

            # de-dupe preserve order
            def uniq(items: list[str]) -> list[str]:
                seen: set[str] = set()
                out: list[str] = []
                for i in items:
                    if i not in seen:
                        seen.add(i)
                        out.append(i)
                return out

            rows.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "endpoint": f"{method.upper()} {path}",
                    "summary": meta.get("summary") or meta.get("operationId") or "",
                    "tags": meta.get("tags") or [],
                    "headers": uniq(headers),
                    "query": uniq(query),
                    "path_params": uniq(path_params),
                    "body_fields": uniq(body_fields),
                    "glob_path": _to_glob(path),
                }
            )
    rows.sort(key=lambda r: (r["path"], r["method"]))
    return rows


def _to_glob(path: str) -> str:
    """Convert OpenAPI `/items/{id}` → `/items/*` for path_matches."""
    import re

    return re.sub(r"\{[^}]+\}", "*", path)


def aggregate_openapi_keys(paths: list[dict[str, Any]]) -> dict[str, list[str]]:
    headers: list[str] = []
    body_fields: list[str] = []
    query: list[str] = []
    for p in paths:
        headers.extend(p.get("headers") or [])
        body_fields.extend(p.get("body_fields") or [])
        query.extend(p.get("query") or [])

    def uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for i in items:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return sorted(out)

    return {
        "headers": uniq(headers),
        "body_fields": uniq(body_fields),
        "query": uniq(query),
        "paths": sorted({p["path"] for p in paths}),
    }
