"""Category evaluation engine."""

from __future__ import annotations

from typing import Any

from monitorit.awatch.analytics.categories.rules import CategoryRule


class CategoryEngine:
    def __init__(
        self,
        rules: list[CategoryRule] | None = None,
        *,
        multi_label: bool = True,
        loader: Any | None = None,
        cache_ttl: float = 60.0,
    ) -> None:
        self._static_rules = list(rules or [])
        self.multi_label = multi_label
        self.loader = loader
        self.cache_ttl = cache_ttl
        self._loaded: list[CategoryRule] = []
        self._loaded_at: float = 0.0

    async def _refresh(self) -> list[CategoryRule]:
        import time

        now = time.monotonic()
        if self.loader and (now - self._loaded_at) >= self.cache_ttl:
            loaded = self.loader()
            if hasattr(loaded, "__await__"):
                loaded = await loaded  # type: ignore[misc]
            self._loaded = list(loaded or [])
            self._loaded_at = now
        return self._static_rules + self._loaded

    async def evaluate(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        query: dict[str, Any],
        body: Any,
        consumer: dict[str, Any] | None,
    ) -> list[str]:
        rules = await self._refresh()
        rules_sorted = sorted(rules, key=lambda r: -r.priority)
        ctx = {
            "method": method,
            "path": path,
            "headers": headers,
            "query": query,
            "body": body,
            "consumer": consumer or {},
        }
        matched: list[str] = []
        for rule in rules_sorted:
            try:
                if rule.when(ctx):
                    matched.append(rule.name)
                    if not self.multi_label:
                        break
            except Exception:  # noqa: BLE001
                continue
        return matched
