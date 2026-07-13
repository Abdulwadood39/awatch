"""Dashboard API router factory."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from monitorit.awatch.analytics.openapi import collect_registered_routes, compute_drift
from monitorit.awatch.api.auth import build_auth_dependency
from monitorit.awatch.core.ui_config import aggregate_openapi_keys, parse_openapi_paths
from monitorit.awatch.privacy.mask import path_matches_exclude
from monitorit.awatch.privacy.scrubbing_report import build_scrubbing_report


class SmtpSettings(BaseModel):
    smtp_url: str | None = None
    from_addr: str | None = "awatch@localhost"
    default_to: list[str] = Field(default_factory=list)


class ExcludePathDef(BaseModel):
    id: str | None = None
    path: str
    enabled: bool = True
    note: str | None = None


class UptimeSettings(BaseModel):
    enabled: bool = True
    path: str = "/health"
    interval_seconds: float = 60.0
    expected_status: int = 200


class PerformanceSettings(BaseModel):
    apdex_t_ms: float = 500.0


def _is_dashboard_path(path: str, dashboard_path: str) -> bool:
    dash = (dashboard_path or "/__awatch").rstrip("/") or "/__awatch"
    return path == dash or path.startswith(dash + "/")


def _filterable_openapi_paths(
    paths: list[dict[str, Any]],
    *,
    exclude_patterns: list[str],
    dashboard_path: str,
) -> list[dict[str, Any]]:
    """OpenAPI ops for filter dropdowns — skips excluded paths and awatch routes."""
    out: list[dict[str, Any]] = []
    for row in paths:
        path = str(row.get("path") or "")
        if not path or _is_dashboard_path(path, dashboard_path):
            continue
        if any(path_matches_exclude(path, ex) for ex in exclude_patterns):
            continue
        out.append(row)
    return out


def create_api_router(watch: Any) -> APIRouter:
    router = APIRouter()
    auth_dep = build_auth_dependency(
        watch.config.auth_token,
        watch.config.auth_dependency,
        env=watch.config.env,
    )

    def _auth():
        return Depends(auth_dep) if auth_dep else None

    def _require_ui_unlocked() -> None:
        if not watch.config.allow_ui_config:
            raise HTTPException(
                status_code=403,
                detail=(
                    "UI configuration is locked. "
                    "Pass allow_ui_config=True to AWatch(...) in code to unlock Settings."
                ),
            )

    @router.get("/api/overview")
    async def overview(_: Any = Depends(auth_dep) if auth_dep else None) -> dict[str, Any]:
        counts = await watch.storage.counts()
        endpoints = await watch.storage.endpoint_stats(hours=24)
        traffic = await watch.storage.traffic_timeline(hours=24)
        total = counts.get("requests") or 0
        err5 = counts.get("errors_5xx") or 0
        avg_latency = 0.0
        if endpoints:
            weighted = sum(e["avg_ms"] * e["count"] for e in endpoints)
            avg_latency = round(weighted / max(total, 1), 2)
        return {
            **counts,
            "error_rate": round(err5 / total, 4) if total else 0.0,
            "avg_latency_ms": avg_latency,
            "endpoint_count": len(endpoints),
            "traffic_points": len(traffic),
            "queue_depth": watch.queue.depth,
            "dropped": watch.queue.dropped,
            "last_flush_age_s": watch.queue.last_flush_age_s,
            "writer_running": watch.queue.running,
            "scrubbing": build_scrubbing_report(watch.privacy),
            "release": watch.config.release,
            "env": watch.config.env,
            "allow_ui_config": watch.config.allow_ui_config,
        }

    @router.get("/api/requests")
    async def list_requests(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        status_code: int | None = None,
        method: str | None = None,
        path_contains: str | None = None,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        category: str | None = None,
        min_duration_ms: float | None = None,
        status_class: str | None = None,
        client_ip: str | None = None,
        hours: int | None = Query(None, ge=1, le=720),
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> list[dict[str, Any]]:
        return await watch.storage.list_requests(
            limit=limit,
            offset=offset,
            status_code=status_code,
            method=method,
            path_contains=path_contains,
            consumer_id=consumer_id,
            consumer_group=consumer_group,
            category=category,
            min_duration_ms=min_duration_ms,
            status_class=status_class,
            client_ip=client_ip,
            hours=hours,
        )

    @router.get("/api/requests/{request_id}")
    async def get_request(
        request_id: str,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        row = await watch.storage.get_request(request_id)
        if not row:
            return {"error": "not_found"}
        row["curl"] = _to_curl(row)
        return row

    @router.get("/api/endpoints")
    async def endpoints(
        hours: int = Query(24, ge=1, le=720),
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> list[dict[str, Any]]:
        return await watch.storage.endpoint_stats(
            hours=hours,
            consumer_id=consumer_id,
            consumer_group=consumer_group,
            apdex_t_ms=watch.config.apdex_t_ms,
        )

    @router.get("/api/traffic")
    async def traffic(
        hours: int = Query(24, ge=1, le=720),
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        summary = await watch.storage.traffic_summary(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        timeline = await watch.storage.traffic_timeline(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        endpoints = await watch.storage.endpoint_stats(
            hours,
            consumer_id=consumer_id,
            consumer_group=consumer_group,
            apdex_t_ms=watch.config.apdex_t_ms,
        )
        return {**summary, "timeline": timeline, "endpoints": endpoints}

    @router.get("/api/performance")
    async def performance(
        hours: int = Query(24, ge=1, le=720),
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        return await watch.storage.performance_summary(
            hours,
            apdex_t_ms=watch.config.apdex_t_ms,
            consumer_id=consumer_id,
            consumer_group=consumer_group,
        )

    @router.get("/api/consumers")
    async def consumers(
        hours: int = Query(24, ge=1, le=720),
        view: str = Query("individuals", pattern="^(individuals|groups)$"),
        group: str | None = None,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        rows = await watch.storage.consumer_stats(hours=hours, view=view, group=group)
        adoption = await watch.storage.consumer_adoption(hours=hours)
        return {"view": view, "group": group, "rows": rows, "adoption": adoption}

    @router.get("/api/validation")
    async def validation(
        hours: int = Query(24, ge=1, le=720),
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> list[dict[str, Any]]:
        return await watch.storage.validation_heatmap(hours=hours)

    @router.get("/api/errors")
    async def errors(
        hours: int = Query(24, ge=1, le=720),
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        status_rows = await watch.storage.status_error_stats(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        fingerprints = await watch.storage.error_groups(hours=hours)
        validation = await watch.storage.validation_heatmap(hours=hours)
        timeline = await watch.storage.traffic_timeline(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        return {
            "status_codes": status_rows,
            "fingerprints": fingerprints,
            "validation": validation,
            "timeline": timeline,
        }

    @router.get("/api/openapi-drift")
    async def openapi_drift(
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        registered = collect_registered_routes(watch.app)
        observed = await watch.storage.observed_routes()
        return compute_drift(registered, observed)

    @router.get("/api/openapi")
    async def openapi_inventory(
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        """Live FastAPI OpenAPI inventory (in-process ``app.openapi()``)."""
        schema = watch.app.openapi()
        paths = parse_openapi_paths(schema)
        filterable = _filterable_openapi_paths(
            paths,
            exclude_patterns=list(watch.privacy.exclude_paths),
            dashboard_path=watch.config.dashboard_path,
        )
        return {
            "title": schema.get("info", {}).get("title"),
            "version": schema.get("info", {}).get("version"),
            "path_count": len(paths),
            "paths": paths,
            "filterable_paths": filterable,
            "keys": aggregate_openapi_keys(filterable),
            "synced_from": "app.openapi()",
            "dashboard_path": watch.config.dashboard_path,
            "note": (
                "filterable_paths excludes awatch dashboard routes and active exclude_paths."
            ),
        }

    @router.get("/api/triggers")
    async def triggers(
        limit: int = Query(100, ge=1, le=500),
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        return {
            "configured": [t.name for t in watch.triggers],
            "code_defined": [t.name for t in watch._code_triggers],
            "history": await watch.storage.list_trigger_history(limit=limit),
        }

    @router.get("/api/scrubbing")
    async def scrubbing(
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        return build_scrubbing_report(watch.privacy)

    # --- Settings / UI config (SMTP, excludes, uptime, performance only) ---

    @router.get("/api/config")
    async def get_config(
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        smtp = await watch.storage.get_ui_config("smtp", {}) or {}
        exclude_paths = await watch.storage.get_ui_config("exclude_paths", []) or []
        safe_smtp = dict(smtp)
        if safe_smtp.get("smtp_url"):
            safe_smtp["smtp_url_set"] = True
        return {
            "allow_ui_config": watch.config.allow_ui_config,
            "locked": not watch.config.allow_ui_config,
            "exclude_paths": exclude_paths,
            "uptime": await watch.storage.get_ui_config("uptime", {}) or {
                "enabled": watch.uptime.enabled,
                "path": watch.uptime.path,
                "interval_seconds": watch.uptime.interval_seconds,
                "expected_status": watch.uptime.expected_status,
            },
            "performance": {
                "apdex_t_ms": watch.config.apdex_t_ms,
                **(await watch.storage.get_ui_config("performance", {}) or {}),
            },
            "code_exclude_paths": list(watch._code_exclude_paths),
            "active_exclude_paths": list(watch.privacy.exclude_paths),
            "smtp": safe_smtp,
            "code_categories": [c.name for c in watch._code_categories],
            "code_triggers": [t.name for t in watch._code_triggers],
            "env": watch.config.env,
            "dashboard_path": watch.config.dashboard_path,
        }

    @router.put("/api/config/smtp")
    async def put_smtp(
        body: SmtpSettings,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        _require_ui_unlocked()
        data = body.model_dump()
        await watch.storage.set_ui_config("smtp", data)
        stats = await watch.reload_runtime_config()
        return {"ok": True, "smtp": data, **stats}

    @router.put("/api/config/exclude-paths")
    async def put_exclude_paths(
        body: list[ExcludePathDef],
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        _require_ui_unlocked()
        items = []
        for item in body:
            data = item.model_dump()
            data["id"] = data.get("id") or str(uuid.uuid4())
            items.append(data)
        await watch.storage.set_ui_config("exclude_paths", items)
        stats = await watch.reload_runtime_config()
        return {
            "ok": True,
            "exclude_paths": items,
            "active_exclude_paths": list(watch.privacy.exclude_paths),
            **stats,
        }

    @router.put("/api/config/uptime")
    async def put_uptime(
        body: UptimeSettings,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        _require_ui_unlocked()
        data = body.model_dump()
        await watch.storage.set_ui_config("uptime", data)
        stats = await watch.reload_runtime_config()
        return {"ok": True, "uptime": data, **stats}

    @router.put("/api/config/performance")
    async def put_performance(
        body: PerformanceSettings,
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        _require_ui_unlocked()
        data = body.model_dump()
        await watch.storage.set_ui_config("performance", data)
        stats = await watch.reload_runtime_config()
        return {"ok": True, "performance": data, **stats}

    @router.get("/api/uptime")
    async def uptime_api(
        hours: int = Query(24, ge=1, le=720),
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        summary = await watch.storage.uptime_summary(hours=hours)
        recent = await watch.storage.list_uptime_checks(hours=hours, limit=200)
        return {
            **summary,
            "recent": recent,
            "config": {
                "enabled": watch.uptime.enabled,
                "path": watch.uptime.path,
                "interval_seconds": watch.uptime.interval_seconds,
                "expected_status": watch.uptime.expected_status,
            },
            "last_result": watch.uptime.last_result,
            "heartbeat_age_s": watch.heartbeat.age_seconds(),
        }

    @router.get("/api/uptime/ping")
    async def uptime_ping() -> dict[str, Any]:
        """External checker endpoint (UptimeRobot/cron). Records an external uptime beat."""
        await watch.uptime.record_external_ping(ok=True, message="ping")
        return {"ok": True, "status": "up"}

    @router.post("/api/config/reload")
    async def reload_config(
        _: Any = Depends(auth_dep) if auth_dep else None,
    ) -> dict[str, Any]:
        stats = await watch.reload_runtime_config()
        return {"ok": True, **stats}

    @router.get("/health")
    async def health() -> dict[str, Any]:
        db_ok = await watch.storage.ping()
        probes = await watch.probes.run_all()
        return {
            "status": "ok" if db_ok and watch.queue.running else "degraded",
            "db": db_ok,
            "writer_running": watch.queue.running,
            "queue_depth": watch.queue.depth,
            "dropped": watch.queue.dropped,
            "last_error": watch.queue.last_error or watch.storage.last_error,
            "heartbeat_age_s": watch.heartbeat.age_seconds(),
            "probes": probes,
            "allow_ui_config": watch.config.allow_ui_config,
        }

    @router.get("/ready")
    async def ready() -> dict[str, Any]:
        ok = watch.storage.ready and watch.queue.running
        return {"ready": ok}

    dash_dir = Path(__file__).resolve().parent.parent / "dashboard"

    @router.get("/")
    async def dashboard_index() -> HTMLResponse:
        index = dash_dir / "index.html"
        return HTMLResponse(index.read_text(encoding="utf-8"))

    return router


def _to_curl(row: dict[str, Any]) -> str:
    method = row.get("method", "GET")
    path = row.get("path", "/")
    headers = row.get("request_headers") or {}
    parts = [f"curl -X {method} 'http://localhost{path}'"]
    for k, v in headers.items():
        if str(v) == "***":
            continue
        parts.append(f"  -H '{k}: {v}'")
    body = row.get("request_body")
    if body:
        parts.append(f"  -d '{body}'")
    return " \\\n".join(parts)
