"""Resolve consumers from request fingerprints (Apitally-style group + identifier)."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from typing import Any


def _parse_body(body: Any) -> Any:
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray)):
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except Exception:
            return None
    return body


def extract_request_value(
    source: str,
    key: str,
    *,
    headers: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
) -> str | None:
    """Pull a string value from header / query / json body (dotted path)."""
    source = (source or "").lower().strip()
    key = (key or "").strip()
    if not key:
        return None

    if source == "header":
        hdrs = {str(k).lower(): v for k, v in (headers or {}).items()}
        val = hdrs.get(key.lower())
        return None if val is None else str(val)

    if source == "query":
        q = query or {}
        if key not in q:
            return None
        val = q[key]
        if isinstance(val, list):
            val = val[0] if val else None
        return None if val is None else str(val)

    if source in {"json", "body", "payload"}:
        data = _parse_body(body)
        if not isinstance(data, dict):
            return None
        parts = [p for p in key.replace("$.", "").split(".") if p]
        cur: Any = data
        for part in parts:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return None if cur is None else str(cur)

    return None


@dataclass
class FieldRef:
    """A single extract from the request (header / query / json)."""

    source: str  # header | query | json
    key: str

    def extract(
        self,
        *,
        headers: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
    ) -> str | None:
        return extract_request_value(
            self.source, self.key, headers=headers, query=query, body=body
        )


@dataclass
class ConsumerRule:
    """Fingerprint rule: identifier (+ optional group/name) extracted from the request."""

    name: str
    identifier: FieldRef
    group: FieldRef | None = None
    name_field: FieldRef | None = None
    method: str = "*"
    path: str = "*"
    enabled: bool = True

    def matches(self, method: str, path: str) -> bool:
        if not self.enabled:
            return False
        if self.method and self.method != "*" and self.method.upper() != method.upper():
            return False
        pattern = self.path or "*"
        if pattern == "*":
            return True
        return fnmatch.fnmatch(path, pattern) or path.startswith(pattern.rstrip("*"))


@dataclass
class ConsumerExtractor:
    """Apply UI fingerprint rules. Explicit set_consumer() always wins."""

    rules: list[ConsumerRule] = field(default_factory=list)

    def set_rules(self, rules: list[ConsumerRule]) -> None:
        self.rules = list(rules)

    def resolve(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
    ) -> dict[str, Any] | None:
        kwargs = {"headers": headers, "query": query, "body": body}
        for rule in self.rules:
            if not rule.matches(method, path):
                continue
            identifier = rule.identifier.extract(**kwargs)
            if not identifier:
                continue
            group = rule.group.extract(**kwargs) if rule.group else None
            display = rule.name_field.extract(**kwargs) if rule.name_field else None
            return {
                "identifier": identifier,
                "name": display or identifier,
                "group": group,
                "rule": rule.name,
            }
        return None


def _field_from_dict(raw: Any) -> FieldRef | None:
    if not isinstance(raw, dict):
        return None
    key = str(raw.get("key") or "").strip()
    if not key:
        return None
    source = str(raw.get("source") or "header").strip().lower()
    if source in {"body", "payload"}:
        source = "json"
    return FieldRef(source=source, key=key)


def compile_consumer_defs(defs: list[dict[str, Any]]) -> list[ConsumerRule]:
    """Compile UI/code consumer fingerprint defs.

    Supports new shape::
        {identifier: {source,key}, group?: {...}, name?: {...}}

    and legacy filters shape::
        {filters: [{source,key}, {source,key}]}  # id then group
    """
    rules: list[ConsumerRule] = []
    for d in defs:
        if not d.get("enabled", True):
            continue

        identifier = _field_from_dict(d.get("identifier"))
        group = _field_from_dict(d.get("group"))
        name_field = _field_from_dict(d.get("name_field") or d.get("display_name"))

        # Legacy: filters[0]=identifier, filters[1]=group
        if identifier is None:
            raw_filters = list(d.get("filters") or [])
            if raw_filters:
                identifier = _field_from_dict(raw_filters[0])
                if len(raw_filters) > 1 and group is None:
                    group = _field_from_dict(raw_filters[1])

        if identifier is None:
            continue

        rules.append(
            ConsumerRule(
                name=str(d.get("name") or "consumer"),
                identifier=identifier,
                group=group,
                name_field=name_field,
                method=str(d.get("method") or "*"),
                path=str(d.get("path") or "*"),
                enabled=True,
            )
        )
    return rules
