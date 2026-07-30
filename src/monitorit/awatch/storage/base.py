"""Storage protocol."""

from __future__ import annotations

from typing import Any, Protocol

from monitorit.awatch.storage.models import RequestRecord, TriggerHistoryRecord


class StorageProtocol(Protocol):
    async def setup(self) -> None: ...

    async def close(self) -> None: ...

    async def insert_request(self, record: RequestRecord) -> None: ...

    async def list_requests(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status_code: int | None = None,
        method: str | None = None,
        path_contains: str | None = None,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        category: str | None = None,
        min_duration_ms: float | None = None,
        status_class: str | None = None,
        client_ip: str | None = None,
        hours: int | None = None,
    ) -> dict[str, Any]: ...

    async def list_outbound_for_parent(
        self, parent_request_id: str
    ) -> list[dict[str, Any]]: ...

    async def get_request(self, request_id: str) -> dict[str, Any] | None: ...

    async def endpoint_stats(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        apdex_t_ms: float = 500.0,
    ) -> list[dict[str, Any]]: ...

    async def traffic_timeline(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def traffic_summary(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> dict[str, Any]: ...

    async def performance_summary(
        self,
        hours: int = 24,
        *,
        apdex_t_ms: float = 500.0,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> dict[str, Any]: ...

    async def consumer_stats(
        self,
        hours: int = 24,
        *,
        view: str = "individuals",
        group: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def consumer_adoption(self, hours: int = 24) -> dict[str, Any]: ...

    async def status_error_stats(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def validation_heatmap(self, hours: int = 24) -> list[dict[str, Any]]: ...

    async def error_groups(self, hours: int = 24) -> list[dict[str, Any]]: ...

    async def insert_trigger_history(self, record: TriggerHistoryRecord) -> None: ...

    async def list_trigger_history(self, limit: int = 100) -> list[dict[str, Any]]: ...

    async def prune(self, max_requests: int, retention_hours: int) -> None: ...

    async def ping(self) -> bool: ...

    async def counts(self) -> dict[str, int]: ...

    async def observed_routes(self) -> set[str]: ...

    async def get_ui_config(self, key: str, default: Any = None) -> Any: ...

    async def set_ui_config(self, key: str, value: Any) -> None: ...

    async def get_all_ui_config(self) -> dict[str, Any]: ...

    async def insert_uptime_check(
        self,
        *,
        kind: str,
        ok: bool,
        latency_ms: float | None = None,
        status_code: int | None = None,
        message: str | None = None,
        path: str | None = None,
        timestamp: str | None = None,
    ) -> None: ...

    async def list_uptime_checks(
        self, hours: int = 24, *, kind: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]: ...

    async def uptime_summary(self, hours: int = 24) -> dict[str, Any]: ...
