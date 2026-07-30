"""AWatch — main integration entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Sequence

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from monitorit.awatch.analytics.categories import CategoryEngine, CategoryRule
from monitorit.awatch.analytics.consumer_rules import ConsumerExtractor
from monitorit.awatch.api.router import create_api_router
from monitorit.awatch.capture.dependencies import instrument_httpx, instrument_sqlalchemy
from monitorit.awatch.capture.logging_bridge import install_log_capture
from monitorit.awatch.capture.middleware import AWatchMiddleware
from monitorit.awatch.core.config import AWatchConfig
from monitorit.awatch.core.constants import DEFAULT_EXCLUDE_PATHS
from monitorit.awatch.health.heartbeat import HeartbeatTracker
from monitorit.awatch.health.probes import ProbeRegistry
from monitorit.awatch.health.uptime import UptimeMonitor
from monitorit.awatch.privacy.mask import PrivacyFilter
from monitorit.awatch.storage.factory import create_storage
from monitorit.awatch.storage.queue import WriteQueue
from monitorit.awatch.triggers.engine import TriggerEngine
from monitorit.awatch.triggers.rules import Trigger

logger = logging.getLogger("awatch")


class AWatch:
    """Attach monitoring to a FastAPI app.

    Example::

        app = FastAPI()
        AWatch(app, env="dev", allow_ui_config=True)  # unlock Settings in dashboard
    """

    def __init__(
        self,
        app: FastAPI,
        *,
        env: str = "dev",
        dashboard_path: str = "/__awatch",
        db_path: str | None = None,
        storage: str = "sqlite",
        database_url: str | None = None,
        postgres_url: str | None = None,
        auth_token: str | None = None,
        auth_dependency: Callable[..., Any] | None = None,
        enable_request_logging: bool = True,
        log_query_params: bool = True,
        log_request_headers: bool = False,
        log_request_body: bool = False,
        log_response_headers: bool = False,
        log_response_body: bool = False,
        capture_logs: bool = False,
        success_sample_rate: float = 1.0,
        slow_threshold_ms: float = 1000.0,
        max_requests: int = 10_000,
        retention_hours: int = 168,
        prune_every: int = 100,
        prune_on_startup: bool = True,
        max_outbound_per_request: int = 50,
        exclude_paths: list[str] | None = None,
        mask_headers: list[str] | None = None,
        mask_query_params: list[str] | None = None,
        mask_body_fields: list[str] | None = None,
        categories: Sequence[CategoryRule] | None = None,
        category_loader: Callable[..., Any] | None = None,
        category_cache_ttl: float = 60.0,
        category_multi_label: bool = True,
        triggers: Sequence[Trigger] | None = None,
        release: str | None = None,
        db_engine: Any | None = None,
        instrument_outbound_http: bool = False,
        allow_ui_config: bool = False,
        quiet_access_logs: bool = True,
        **extra: Any,
    ) -> None:
        self.app = app
        self._code_categories = list(categories or [])
        self._code_triggers = list(triggers or [])

        cfg_kwargs: dict[str, Any] = {
            "env": env,
            "dashboard_path": dashboard_path,
            "db_path": db_path,
            "storage": storage,
            "database_url": database_url,
            "postgres_url": postgres_url,
            "auth_token": auth_token,
            "auth_dependency": auth_dependency,
            "enable_request_logging": enable_request_logging,
            "log_query_params": log_query_params,
            "log_request_headers": log_request_headers,
            "log_request_body": log_request_body,
            "log_response_headers": log_response_headers,
            "log_response_body": log_response_body,
            "capture_logs": capture_logs,
            "success_sample_rate": success_sample_rate,
            "slow_threshold_ms": slow_threshold_ms,
            "max_requests": max_requests,
            "retention_hours": retention_hours,
            "prune_every": prune_every,
            "prune_on_startup": prune_on_startup,
            "max_outbound_per_request": max_outbound_per_request,
            "instrument_outbound_http": instrument_outbound_http,
            "release": release,
            "category_loader": category_loader,
            "category_cache_ttl": category_cache_ttl,
            "category_multi_label": category_multi_label,
            "allow_ui_config": allow_ui_config,
            "quiet_access_logs": quiet_access_logs,
        }
        if exclude_paths is not None:
            cfg_kwargs["exclude_paths"] = exclude_paths
        if mask_headers is not None:
            cfg_kwargs["mask_headers"] = mask_headers
        if mask_query_params is not None:
            cfg_kwargs["mask_query_params"] = mask_query_params
        if mask_body_fields is not None:
            cfg_kwargs["mask_body_fields"] = mask_body_fields
        cfg_kwargs.update(extra)

        self.config = AWatchConfig(**cfg_kwargs)
        self.config.validate_auth()
        self._code_exclude_paths = list(self.config.exclude_paths)

        self.privacy = PrivacyFilter(
            mask_headers=self.config.mask_headers,
            mask_query_params=self.config.mask_query_params,
            mask_body_fields=self.config.mask_body_fields,
            exclude_paths=list(DEFAULT_EXCLUDE_PATHS) + self._code_exclude_paths,
            dashboard_path=self.config.dashboard_path,
        )

        self.storage = create_storage(self.config)
        self.probes = ProbeRegistry()
        self.heartbeat = HeartbeatTracker()
        self.triggers = list(self._code_triggers)

        self.category_engine = CategoryEngine(
            list(self._code_categories),
            multi_label=self.config.category_multi_label,
            loader=self.config.category_loader,
            cache_ttl=self.config.category_cache_ttl,
        )
        self.consumer_extractor = ConsumerExtractor()

        self.queue = WriteQueue(
            self.storage,
            max_requests=self.config.max_requests,
            retention_hours=self.config.retention_hours,
            prune_every=self.config.prune_every,
            on_request=self._on_persisted_request,
        )
        self.trigger_engine = TriggerEngine(self.triggers, self.queue)

        base_url = self.config.uptime_base_url or "http://127.0.0.1:8000"
        self.uptime = UptimeMonitor(
            storage=self.storage,
            base_url=base_url,
            path=self.config.uptime_path,
            interval_seconds=self.config.uptime_interval_seconds,
            expected_status=self.config.uptime_expected_status,
            enabled=self.config.uptime_enabled,
        )
        self.uptime.set_heartbeat_source(self.heartbeat.age_seconds)

        install_log_capture()

        if self.config.quiet_access_logs:
            from monitorit.awatch.capture.access_log import install_quiet_access_logs

            install_quiet_access_logs(
                dashboard_path=self.config.dashboard_path,
                extra_paths=[
                    self.config.uptime_path,
                    "/health",
                    "/healthz",
                    "/ready",
                    "/readyz",
                    "/livez",
                ],
            )

        if db_engine is not None:
            instrument_sqlalchemy(db_engine)
        if self.config.instrument_outbound_http:
            instrument_httpx(queue=self.queue, config=self.config, privacy=self.privacy)

        api_router = create_api_router(self)
        app.include_router(api_router, prefix=self.config.dashboard_path)

        assets = Path(__file__).resolve().parent.parent / "dashboard" / "assets"
        if assets.exists():
            app.mount(
                f"{self.config.dashboard_path}/assets",
                StaticFiles(directory=str(assets)),
                name="awatch-assets",
            )

        app.add_middleware(
            AWatchMiddleware,
            config=self.config,
            privacy=self.privacy,
            queue=self.queue,
            category_engine=self.category_engine,
            trigger_engine=self.trigger_engine,
            consumer_extractor=self.consumer_extractor,
        )

        self._install_lifespan(app)
        app.state.awatch = self
        logger.info(
            "awatch ready — dashboard at %s (env=%s, storage=%s, ui_config=%s)",
            self.config.dashboard_path,
            self.config.env,
            self.config.storage,
            "unlocked" if self.config.allow_ui_config else "locked",
        )

    async def _on_persisted_request(self, record: Any) -> None:
        if getattr(record, "direction", "inbound") != "outbound":
            self.heartbeat.beat()

    def register_probe(self, name: str, fn: Callable[..., Any]) -> None:
        self.probes.register(name, fn)

    async def reload_runtime_config(self) -> dict[str, Any]:
        """Reload UI-stored SMTP / excludes / uptime / performance / retention."""
        smtp = await self.storage.get_ui_config("smtp", {}) or {}
        ui_excludes = await self.storage.get_ui_config("exclude_paths", []) or []
        uptime_cfg = await self.storage.get_ui_config("uptime", {}) or {}
        performance_cfg = await self.storage.get_ui_config("performance", {}) or {}
        retention_cfg = await self.storage.get_ui_config("retention", {}) or {}

        self.category_engine._static_rules = list(self._code_categories)
        self.category_engine._loaded_at = 0.0
        self.triggers = list(self._code_triggers)
        self.trigger_engine.triggers = self.triggers
        self.consumer_extractor.set_rules([])

        if performance_cfg.get("apdex_t_ms") is not None:
            self.config.apdex_t_ms = float(performance_cfg["apdex_t_ms"])

        self.queue.configure_retention(
            max_requests=retention_cfg.get("max_requests", self.config.max_requests),
            retention_hours=retention_cfg.get("retention_hours", self.config.retention_hours),
            prune_every=retention_cfg.get("prune_every", self.config.prune_every),
        )
        if retention_cfg.get("max_requests") is not None:
            self.config.max_requests = int(retention_cfg["max_requests"])
        if retention_cfg.get("retention_hours") is not None:
            self.config.retention_hours = int(retention_cfg["retention_hours"])
        if retention_cfg.get("prune_every") is not None:
            self.config.prune_every = max(1, int(retention_cfg["prune_every"]))

        self.uptime.configure(
            path=uptime_cfg.get("path") or self.config.uptime_path,
            interval_seconds=uptime_cfg.get("interval_seconds") or self.config.uptime_interval_seconds,
            expected_status=uptime_cfg.get("expected_status") or self.config.uptime_expected_status,
            enabled=uptime_cfg.get("enabled") if "enabled" in uptime_cfg else self.config.uptime_enabled,
        )

        ui_exclude_list = [
            str(x.get("path") if isinstance(x, dict) else x).strip()
            for x in ui_excludes
            if (x.get("path") if isinstance(x, dict) else x)
            and (x.get("enabled", True) if isinstance(x, dict) else True)
        ]
        self.privacy.set_exclude_paths(
            list(DEFAULT_EXCLUDE_PATHS) + self._code_exclude_paths + ui_exclude_list
        )

        return {
            "categories": len(self.category_engine._static_rules),
            "triggers": len(self.triggers),
            "exclude_paths": len(self.privacy.exclude_paths),
            "smtp_configured": bool(smtp.get("smtp_url")),
            "apdex_t_ms": self.config.apdex_t_ms,
            "uptime_enabled": self.uptime.enabled,
            "max_requests": self.queue.max_requests,
            "retention_hours": self.queue.retention_hours,
            "prune_every": self.queue.prune_every,
        }

    def _install_lifespan(self, app: FastAPI) -> None:
        original = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app_: FastAPI):
            await self.storage.setup()
            await self.reload_runtime_config()
            if self.config.prune_on_startup:
                try:
                    await self.queue.prune_now()
                except Exception:  # noqa: BLE001
                    logger.exception("awatch startup prune failed")
            self.queue.start()
            await self.uptime.start()
            try:
                if original is not None:
                    async with original(app_) as state:
                        yield state
                else:
                    yield
            finally:
                await self.uptime.stop()
                await self.queue.stop()
                await self.storage.close()

        app.router.lifespan_context = lifespan
