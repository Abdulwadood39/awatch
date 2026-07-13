"""AWatch configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from pydantic import BaseModel, Field

from monitorit.awatch.core.constants import (
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_DB_FILENAME,
    DEFAULT_EXCLUDE_PATHS,
    DEFAULT_MASK_BODY_FIELDS,
    DEFAULT_MASK_HEADERS,
    DEFAULT_MASK_QUERY,
    MAX_BODY_BYTES,
)


class AWatchConfig(BaseModel):
    env: str = "dev"
    dashboard_path: str = DEFAULT_DASHBOARD_PATH
    db_path: str | None = None
    storage: str = "sqlite"  # sqlite | postgres
    postgres_url: str | None = None

    # Retention
    max_requests: int = 10_000
    retention_hours: int = 168  # 7 days
    success_sample_rate: float = 1.0
    slow_threshold_ms: float = 1000.0

    # Request logging (opt-in for sensitive parts)
    enable_request_logging: bool = True
    log_query_params: bool = True
    log_request_headers: bool = False
    log_request_body: bool = False
    log_response_headers: bool = False
    log_response_body: bool = False
    log_exception: bool = True
    capture_logs: bool = False
    max_body_bytes: int = MAX_BODY_BYTES

    # Privacy
    mask_headers: list[str] = Field(default_factory=lambda: list(DEFAULT_MASK_HEADERS))
    mask_query_params: list[str] = Field(default_factory=lambda: list(DEFAULT_MASK_QUERY))
    mask_body_fields: list[str] = Field(default_factory=lambda: list(DEFAULT_MASK_BODY_FIELDS))
    exclude_paths: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_PATHS))

    # Auth
    auth_token: str | None = None
    auth_dependency: Any | None = None

    # Release / version
    release: str | None = None

    # Categories & triggers (populated by AWatch)
    category_rules: list[Any] = Field(default_factory=list)
    category_loader: Callable[..., Any] | None = None
    category_cache_ttl: float = 60.0
    category_multi_label: bool = True
    triggers: list[Any] = Field(default_factory=list)

    # UI configuration lock — False = Settings read-only in dashboard
    allow_ui_config: bool = False

    # Performance / Apdex threshold (ms)
    apdex_t_ms: float = 500.0

    # Uptime synthetic checks
    uptime_enabled: bool = True
    uptime_path: str = "/health"
    uptime_interval_seconds: float = 60.0
    uptime_expected_status: int = 200
    uptime_base_url: str | None = None  # default http://127.0.0.1:{port} inferred later

    model_config = {"arbitrary_types_allowed": True}

    def resolved_db_path(self) -> Path:
        if self.db_path:
            p = Path(self.db_path)
            if p.suffix:
                return p
            return p / DEFAULT_DB_FILENAME
        return Path.cwd() / DEFAULT_DB_FILENAME

    def is_prod(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    def validate_auth(self) -> None:
        if self.is_prod() and not self.auth_token and self.auth_dependency is None:
            raise RuntimeError(
                "awatch: env is production but no auth_token or auth_dependency was provided. "
                "Pass auth_token=... or auth_dependency=... to protect the dashboard."
            )


def build_config(**kwargs: Any) -> AWatchConfig:
    return AWatchConfig(**{k: v for k, v in kwargs.items() if v is not None or k in kwargs})
