"""Trigger event types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TriggerEvent:
    kind: str
    fingerprint: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
