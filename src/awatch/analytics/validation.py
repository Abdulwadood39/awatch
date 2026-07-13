"""422 validation error extraction."""

from __future__ import annotations

import json
from typing import Any


def extract_validation_errors(body: bytes | str | None) -> list[dict[str, Any]]:
    if not body:
        return []
    if isinstance(body, bytes):
        try:
            text = body.decode("utf-8")
        except Exception:
            return []
    else:
        text = body
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    detail = data.get("detail") if isinstance(data, dict) else None
    if not isinstance(detail, list):
        return []

    out: list[dict[str, Any]] = []
    for item in detail:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "loc": item.get("loc", []),
                "msg": item.get("msg", ""),
                "type": item.get("type", ""),
            }
        )
    return out
