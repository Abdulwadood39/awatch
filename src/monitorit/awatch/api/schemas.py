"""Pydantic response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class OverviewResponse(BaseModel):
    requests: int
    errors_5xx: int
    validation_422: int
    queue_depth: int
    dropped: int
    scrubbing: dict[str, Any]
    release: str | None = None
