"""In-process aggregator helpers (thin; durable stats live in storage)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class Aggregator:
    def __init__(self) -> None:
        self.total = 0
        self.by_status: dict[int, int] = defaultdict(int)

    def observe(self, status_code: int) -> None:
        self.total += 1
        self.by_status[status_code] += 1

    def snapshot(self) -> dict[str, Any]:
        return {"total": self.total, "by_status": dict(self.by_status)}
