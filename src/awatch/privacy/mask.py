"""Privacy: masking and exclusion."""

from __future__ import annotations

import fnmatch
import json
import re
from typing import Any, Iterable

from awatch.core.constants import MASKED


def _compile(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def name_matches(name: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(name) for p in patterns)


def path_matches_exclude(path: str, pattern: str) -> bool:
    """Match a path against an exclude rule.

    Supported forms:
    - exact / prefix: ``/auth`` or ``/auth/login`` (also matches children)
    - glob: ``/users/*/password``, ``/internal/**``
    - regex: patterns starting with ``^`` or ending with ``$``
    """
    pattern = (pattern or "").strip()
    if not pattern:
        return False

    # Regex
    if pattern.startswith("^") or pattern.endswith("$"):
        try:
            return re.search(pattern, path) is not None
        except re.error:
            return path == pattern

    # Glob (fnmatch; treat ** as * for simplicity)
    if any(ch in pattern for ch in "*?[]"):
        normalized = pattern.replace("**", "*")
        if fnmatch.fnmatch(path, normalized):
            return True
        # also allow prefix-glob like /private/*
        return fnmatch.fnmatch(path.rstrip("/"), normalized.rstrip("/"))

    # Exact or prefix
    if path == pattern:
        return True
    prefix = pattern if pattern.endswith("/") else pattern + "/"
    return path.startswith(prefix)


class PrivacyFilter:
    def __init__(
        self,
        mask_headers: list[str] | None = None,
        mask_query_params: list[str] | None = None,
        mask_body_fields: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        dashboard_path: str = "/__awatch",
    ) -> None:
        self.header_patterns = _compile(mask_headers or [])
        self.query_patterns = _compile(mask_query_params or [])
        self.body_patterns = _compile(mask_body_fields or [])
        self.exclude_paths = list(exclude_paths or [])
        self.dashboard_path = dashboard_path.rstrip("/") or "/__awatch"
        self.scrub_counts: dict[str, int] = {
            "headers": 0,
            "query": 0,
            "body_fields": 0,
        }

    def set_exclude_paths(self, paths: list[str]) -> None:
        """Replace the active exclude list (used when UI config reloads)."""
        # Deduplicate while preserving order
        seen: set[str] = set()
        merged: list[str] = []
        for p in paths:
            p = str(p).strip()
            if not p or p in seen:
                continue
            seen.add(p)
            merged.append(p)
        self.exclude_paths = merged

    def should_exclude(self, path: str) -> bool:
        if path == self.dashboard_path or path.startswith(self.dashboard_path + "/"):
            return True
        # Browser / tooling noise that should never enter analytics
        if path.startswith("/.well-known/"):
            return True
        return any(path_matches_exclude(path, ex) for ex in self.exclude_paths)

    def mask_headers(self, headers: dict[str, str] | None) -> dict[str, str] | None:
        if not headers:
            return headers
        out: dict[str, str] = {}
        for k, v in headers.items():
            if name_matches(k, self.header_patterns):
                out[k] = MASKED
                self.scrub_counts["headers"] += 1
            else:
                out[k] = v
        return out

    def mask_query(self, query: dict[str, Any] | None) -> dict[str, Any] | None:
        if not query:
            return query
        out: dict[str, Any] = {}
        for k, v in query.items():
            if name_matches(k, self.query_patterns):
                out[k] = MASKED
                self.scrub_counts["query"] += 1
            else:
                out[k] = v
        return out

    def mask_body(self, body: bytes | str | None) -> str | None:
        if body is None:
            return None
        if isinstance(body, bytes):
            try:
                text = body.decode("utf-8", errors="replace")
            except Exception:
                return MASKED
        else:
            text = body
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
        masked = self._mask_json(data)
        return json.dumps(masked, default=str)

    def _mask_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():
                if name_matches(str(k), self.body_patterns):
                    out[k] = MASKED
                    self.scrub_counts["body_fields"] += 1
                else:
                    out[k] = self._mask_json(v)
            return out
        if isinstance(data, list):
            return [self._mask_json(i) for i in data]
        return data

    def report(self) -> dict[str, int]:
        return dict(self.scrub_counts)
