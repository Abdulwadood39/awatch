"""Storage data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RequestRecord:
    request_id: str
    timestamp: str
    method: str
    path: str
    route: str | None
    status_code: int
    duration_ms: float
    client_ip: str | None = None
    user_agent: str | None = None
    request_size: int = 0
    response_size: int = 0
    query_params: dict[str, Any] | None = None
    request_headers: dict[str, str] | None = None
    response_headers: dict[str, str] | None = None
    request_body: str | None = None
    response_body: str | None = None
    exception: str | None = None
    exception_type: str | None = None
    consumer_id: str | None = None
    consumer_name: str | None = None
    consumer_group: str | None = None
    categories: list[str] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    spans: list[dict[str, Any]] = field(default_factory=list)
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    release: str | None = None
    error_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricBucket:
    endpoint: str  # METHOD path_template
    window_start: str
    count: int = 0
    error_count: int = 0
    status_2xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    total_duration_ms: float = 0.0
    durations: list[float] = field(default_factory=list)

    def add(self, status: int, duration_ms: float) -> None:
        self.count += 1
        self.total_duration_ms += duration_ms
        self.durations.append(duration_ms)
        if 200 <= status < 300:
            self.status_2xx += 1
        elif 400 <= status < 500:
            self.status_4xx += 1
            if status >= 400:
                self.error_count += 1
        elif status >= 500:
            self.status_5xx += 1
            self.error_count += 1


@dataclass
class TriggerHistoryRecord:
    trigger_name: str
    timestamp: str
    success: bool
    message: str
    fingerprint: str
    details: dict[str, Any] = field(default_factory=dict)
