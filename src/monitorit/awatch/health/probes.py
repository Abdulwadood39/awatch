"""Health probes registry."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

ProbeFn = Callable[[], Awaitable[bool] | bool]


class ProbeRegistry:
    def __init__(self) -> None:
        self._probes: dict[str, ProbeFn] = {}

    def register(self, name: str, fn: ProbeFn) -> None:
        self._probes[name] = fn

    async def run_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, fn in self._probes.items():
            start = time.perf_counter()
            try:
                result = fn()
                if hasattr(result, "__await__"):
                    ok = await result  # type: ignore[misc]
                else:
                    ok = bool(result)
                results[name] = {
                    "ok": bool(ok),
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            except Exception as exc:  # noqa: BLE001
                results[name] = {
                    "ok": False,
                    "error": str(exc),
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                }
        return results
