"""Category matchers and rules."""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class Condition(Protocol):
    def __call__(self, ctx: dict[str, Any]) -> bool: ...


@dataclass
class _And:
    left: Any
    right: Any

    def __call__(self, ctx: dict[str, Any]) -> bool:
        return bool(self.left(ctx) and self.right(ctx))

    def __and__(self, other: Any) -> _And:
        return _And(self, other)

    def __or__(self, other: Any) -> _Or:
        return _Or(self, other)


@dataclass
class _Or:
    left: Any
    right: Any

    def __call__(self, ctx: dict[str, Any]) -> bool:
        return bool(self.left(ctx) or self.right(ctx))

    def __and__(self, other: Any) -> _And:
        return _And(self, other)

    def __or__(self, other: Any) -> _Or:
        return _Or(self, other)


@dataclass
class _Cond:
    fn: Callable[[dict[str, Any]], bool]

    def __call__(self, ctx: dict[str, Any]) -> bool:
        return self.fn(ctx)

    def __and__(self, other: Any) -> _And:
        return _And(self, other)

    def __or__(self, other: Any) -> _Or:
        return _Or(self, other)


def header_equals(name: str, value: str) -> _Cond:
    name_l = name.lower()

    def _fn(ctx: dict[str, Any]) -> bool:
        headers = {k.lower(): v for k, v in (ctx.get("headers") or {}).items()}
        actual = headers.get(name_l)
        if actual is None:
            return False
        if value == "*":
            return True
        return str(actual) == value

    return _Cond(_fn)


def path_prefix(prefix: str) -> _Cond:
    def _fn(ctx: dict[str, Any]) -> bool:
        return str(ctx.get("path", "")).startswith(prefix)

    return _Cond(_fn)


def path_matches(pattern: str) -> _Cond:
    def _fn(ctx: dict[str, Any]) -> bool:
        return fnmatch.fnmatch(str(ctx.get("path", "")), pattern)

    return _Cond(_fn)


def method_in(*methods: str) -> _Cond:
    allowed = {m.upper() for m in methods}

    def _fn(ctx: dict[str, Any]) -> bool:
        return str(ctx.get("method", "")).upper() in allowed

    return _Cond(_fn)


def json_path_equals(dotted: str, value: Any) -> _Cond:
    """Match JSON body field. Use $.plan or plan.nested style paths."""

    parts = [p for p in dotted.replace("$.", "").split(".") if p]

    def _fn(ctx: dict[str, Any]) -> bool:
        body = ctx.get("body")
        if body is None:
            return False
        if isinstance(body, (bytes, bytearray)):
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                return False
        elif isinstance(body, str):
            try:
                data = json.loads(body)
            except Exception:
                return False
        else:
            data = body
        cur: Any = data
        for p in parts:
            if not isinstance(cur, dict) or p not in cur:
                return False
            cur = cur[p]
        return cur == value

    return _Cond(_fn)


def query_equals(name: str, value: str) -> _Cond:
    def _fn(ctx: dict[str, Any]) -> bool:
        q = ctx.get("query") or {}
        return str(q.get(name)) == value

    return _Cond(_fn)


def consumer_group_equals(group: str) -> _Cond:
    def _fn(ctx: dict[str, Any]) -> bool:
        consumer = ctx.get("consumer") or {}
        return consumer.get("group") == group

    return _Cond(_fn)


@dataclass(order=True)
class CategoryRule:
    priority: int
    name: str = field(compare=False)
    when: Any = field(compare=False)

    def __init__(self, name: str, when: Any, priority: int = 0) -> None:
        self.name = name
        self.when = when
        self.priority = priority
