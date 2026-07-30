"""Optional MySQL storage (requires monitorit[mysql])."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from monitorit.awatch.storage.migrations import SCHEMA_VERSION
from monitorit.awatch.storage.models import RequestRecord, TriggerHistoryRecord

INBOUND_FILTER = "(direction IS NULL OR direction = 'inbound')"

SUMMARY_COLUMNS = (
    "request_id, timestamp, method, path, route, status_code, duration_ms, "
    "consumer_id, consumer_group, client_ip, direction, parent_request_id, "
    "consumer_name, exception_type, error_fingerprint, categories, release"
)

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS awatch_meta (
        `key` VARCHAR(255) PRIMARY KEY,
        value TEXT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS ui_config (
        `key` VARCHAR(255) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS requests (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128) NOT NULL,
        timestamp VARCHAR(64) NOT NULL,
        method VARCHAR(16) NOT NULL,
        path TEXT NOT NULL,
        route TEXT,
        status_code INT NOT NULL,
        duration_ms DOUBLE NOT NULL,
        client_ip VARCHAR(128),
        user_agent TEXT,
        request_size INT DEFAULT 0,
        response_size INT DEFAULT 0,
        query_params MEDIUMTEXT,
        request_headers MEDIUMTEXT,
        response_headers MEDIUMTEXT,
        request_body MEDIUMTEXT,
        response_body MEDIUMTEXT,
        exception MEDIUMTEXT,
        exception_type VARCHAR(255),
        consumer_id VARCHAR(255),
        consumer_name VARCHAR(255),
        consumer_group VARCHAR(255),
        categories TEXT,
        logs MEDIUMTEXT,
        spans MEDIUMTEXT,
        validation_errors MEDIUMTEXT,
        `release` VARCHAR(255),
        error_fingerprint VARCHAR(255),
        direction VARCHAR(32) NOT NULL DEFAULT 'inbound',
        parent_request_id VARCHAR(128),
        UNIQUE KEY uq_requests_request_id (request_id),
        KEY idx_requests_timestamp (timestamp),
        KEY idx_requests_status (status_code),
        KEY idx_requests_consumer (consumer_id),
        KEY idx_requests_consumer_group (consumer_group),
        KEY idx_requests_fingerprint (error_fingerprint),
        KEY idx_requests_direction (direction),
        KEY idx_requests_parent (parent_request_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS trigger_history (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        trigger_name VARCHAR(255) NOT NULL,
        timestamp VARCHAR(64) NOT NULL,
        success TINYINT NOT NULL,
        message TEXT,
        fingerprint VARCHAR(255),
        details MEDIUMTEXT,
        KEY idx_trigger_ts (timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS app_logs (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128),
        timestamp VARCHAR(64) NOT NULL,
        level VARCHAR(32),
        logger VARCHAR(255),
        message TEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS uptime_checks (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        timestamp VARCHAR(64) NOT NULL,
        kind VARCHAR(64) NOT NULL,
        ok TINYINT NOT NULL,
        latency_ms DOUBLE,
        status_code INT,
        message TEXT,
        path TEXT,
        KEY idx_uptime_ts (timestamp),
        KEY idx_uptime_kind (kind)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def _json_dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, default=str)


def _json_loads(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _parse_mysql_url(url: str) -> dict[str, Any]:
    # Accept mysql://, mysql+asyncmy://, mariadb://
    normalized = url
    for prefix in ("mysql+asyncmy://", "mysql+aiomysql://", "mariadb://"):
        if normalized.startswith(prefix):
            normalized = "mysql://" + normalized[len(prefix) :]
            break
    parsed = urlparse(normalized)
    if parsed.scheme not in {"mysql", "mariadb", ""}:
        # Still try if user passed host-style without scheme handled above
        pass
    db = (parsed.path or "").lstrip("/")
    if "?" in db:
        db = db.split("?", 1)[0]
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "db": db or None,
        "charset": "utf8mb4",
        "autocommit": False,
    }


class MySQLStorage:
    def __init__(self, url: str) -> None:
        try:
            import asyncmy  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "MySQL storage requires asyncmy. "
                "Install with: pip install monitorit[mysql]"
            ) from exc
        self.url = url
        self._conn: Any = None
        self.ready = False
        self.last_error: str | None = None

    async def setup(self) -> None:
        import asyncmy
        from asyncmy.cursors import DictCursor

        params = _parse_mysql_url(self.url)
        self._conn = await asyncmy.connect(**params)
        async with self._conn.cursor(DictCursor) as cur:
            for stmt in SCHEMA_STATEMENTS:
                await cur.execute(stmt)
            await cur.execute(
                "INSERT INTO awatch_meta(`key`, value) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE value = VALUES(value)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
        await self._conn.commit()
        self.ready = True

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            ensure_closed = getattr(self._conn, "ensure_closed", None)
            if ensure_closed is not None:
                await ensure_closed()
            self._conn = None
            self.ready = False

    @property
    def conn(self) -> Any:
        if not self._conn:
            raise RuntimeError("MySQLStorage not initialized")
        return self._conn

    async def _execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> Any:
        from asyncmy.cursors import DictCursor

        cur = self.conn.cursor(DictCursor)
        await cur.execute(sql, params or ())
        return cur

    async def ping(self) -> bool:
        try:
            cur = await self._execute("SELECT 1 AS ok")
            await cur.fetchone()
            await cur.close()
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return False

    async def insert_request(self, record: RequestRecord) -> None:
        r = record
        cur = await self._execute(
            """
            INSERT INTO requests (
                request_id, timestamp, method, path, route, status_code, duration_ms,
                client_ip, user_agent, request_size, response_size,
                query_params, request_headers, response_headers, request_body, response_body,
                exception, exception_type, consumer_id, consumer_name, consumer_group,
                categories, logs, spans, validation_errors, `release`, error_fingerprint,
                direction, parent_request_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                timestamp = VALUES(timestamp),
                method = VALUES(method),
                path = VALUES(path),
                route = VALUES(route),
                status_code = VALUES(status_code),
                duration_ms = VALUES(duration_ms),
                client_ip = VALUES(client_ip),
                user_agent = VALUES(user_agent),
                request_size = VALUES(request_size),
                response_size = VALUES(response_size),
                query_params = VALUES(query_params),
                request_headers = VALUES(request_headers),
                response_headers = VALUES(response_headers),
                request_body = VALUES(request_body),
                response_body = VALUES(response_body),
                exception = VALUES(exception),
                exception_type = VALUES(exception_type),
                consumer_id = VALUES(consumer_id),
                consumer_name = VALUES(consumer_name),
                consumer_group = VALUES(consumer_group),
                categories = VALUES(categories),
                logs = VALUES(logs),
                spans = VALUES(spans),
                validation_errors = VALUES(validation_errors),
                `release` = VALUES(`release`),
                error_fingerprint = VALUES(error_fingerprint),
                direction = VALUES(direction),
                parent_request_id = VALUES(parent_request_id)
            """,
            (
                r.request_id,
                r.timestamp,
                r.method,
                r.path,
                r.route,
                r.status_code,
                r.duration_ms,
                r.client_ip,
                r.user_agent,
                r.request_size,
                r.response_size,
                _json_dumps(r.query_params),
                _json_dumps(r.request_headers),
                _json_dumps(r.response_headers),
                r.request_body,
                r.response_body,
                r.exception,
                r.exception_type,
                r.consumer_id,
                r.consumer_name,
                r.consumer_group,
                _json_dumps(r.categories),
                _json_dumps(r.logs),
                _json_dumps(r.spans),
                _json_dumps(r.validation_errors),
                r.release,
                r.error_fingerprint,
                r.direction or "inbound",
                r.parent_request_id,
            ),
        )
        await cur.close()
        await self.conn.commit()

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        d = dict(row)
        for key in (
            "query_params",
            "request_headers",
            "response_headers",
            "categories",
            "logs",
            "spans",
            "validation_errors",
        ):
            if key in d:
                d[key] = _json_loads(d.get(key))
        return d

    def _build_request_filters(
        self,
        *,
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
        inbound_only: bool = True,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if inbound_only:
            clauses.append(INBOUND_FILTER)
        if hours is not None:
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            clauses.append("timestamp >= %s")
            params.append(since)
        if status_code is not None:
            clauses.append("status_code = %s")
            params.append(status_code)
        if status_class == "4xx":
            clauses.append("status_code >= 400 AND status_code < 500")
        elif status_class == "5xx":
            clauses.append("status_code >= 500")
        elif status_class == "2xx":
            clauses.append("status_code >= 200 AND status_code < 300")
        if method:
            clauses.append("method = %s")
            params.append(method.upper())
        if path_contains:
            clauses.append("path LIKE %s")
            params.append(f"%{path_contains}%")
        if consumer_id:
            clauses.append("consumer_id = %s")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = %s")
            params.append(consumer_group)
        if category:
            clauses.append("categories LIKE %s")
            params.append(f'%"{category}"%')
        if min_duration_ms is not None:
            clauses.append("duration_ms >= %s")
            params.append(min_duration_ms)
        if client_ip:
            clauses.append("client_ip = %s")
            params.append(client_ip)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

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
    ) -> dict[str, Any]:
        where, params = self._build_request_filters(
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
            inbound_only=True,
        )
        cur = await self._execute(f"SELECT COUNT(*) AS c FROM requests {where}", params)
        total = int((await cur.fetchone())["c"])
        await cur.close()
        page_params = list(params)
        page_params.extend([limit, offset])
        cur = await self._execute(
            f"""
            SELECT {SUMMARY_COLUMNS}
            FROM requests {where}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
            """,
            page_params,
        )
        rows = await cur.fetchall()
        await cur.close()
        items = []
        for row in rows:
            d = dict(row)
            if "categories" in d:
                d["categories"] = _json_loads(d.get("categories"))
            items.append(d)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def list_outbound_for_parent(self, parent_request_id: str) -> list[dict[str, Any]]:
        cur = await self._execute(
            f"""
            SELECT {SUMMARY_COLUMNS}
            FROM requests
            WHERE parent_request_id = %s AND direction = 'outbound'
            ORDER BY timestamp ASC
            """,
            (parent_request_id,),
        )
        rows = await cur.fetchall()
        await cur.close()
        items = []
        for row in rows:
            d = dict(row)
            if "categories" in d:
                d["categories"] = _json_loads(d.get("categories"))
            items.append(d)
        return items

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        cur = await self._execute(
            "SELECT * FROM requests WHERE request_id = %s", (request_id,)
        )
        row = await cur.fetchone()
        await cur.close()
        return self._row_to_dict(row) if row else None

    def _analytics_where(
        self,
        hours: int,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        extra: list[str] | None = None,
    ) -> tuple[str, list[Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = [INBOUND_FILTER, "timestamp >= %s"]
        params: list[Any] = [since]
        if consumer_id:
            clauses.append("consumer_id = %s")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = %s")
            params.append(consumer_group)
        if extra:
            clauses.extend(extra)
        return " AND ".join(clauses), params

    async def endpoint_stats(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        apdex_t_ms: float = 500.0,
    ) -> list[dict[str, Any]]:
        where, params = self._analytics_where(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        cur = await self._execute(
            f"""
            SELECT method, COALESCE(route, path) AS endpoint, status_code, duration_ms,
                   request_size, response_size
            FROM requests WHERE {where}
            """,
            params,
        )
        rows = await cur.fetchall()
        await cur.close()
        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = f"{row['method']} {row['endpoint']}"
            b = buckets.setdefault(
                key,
                {
                    "endpoint": key,
                    "count": 0,
                    "error_count": 0,
                    "status_2xx": 0,
                    "status_4xx": 0,
                    "status_5xx": 0,
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "durations": [],
                },
            )
            b["count"] += 1
            status = row["status_code"]
            dur = float(row["duration_ms"])
            b["durations"].append(dur)
            b["bytes_in"] += int(row["request_size"] or 0)
            b["bytes_out"] += int(row["response_size"] or 0)
            if 200 <= status < 300:
                b["status_2xx"] += 1
            elif 400 <= status < 500:
                b["status_4xx"] += 1
                b["error_count"] += 1
            elif status >= 500:
                b["status_5xx"] += 1
                b["error_count"] += 1
        out = []
        for b in buckets.values():
            durs = b.pop("durations")
            satisfied = sum(1 for d in durs if d <= apdex_t_ms)
            tolerating = sum(1 for d in durs if apdex_t_ms < d <= 4 * apdex_t_ms)
            apdex = ((satisfied + tolerating * 0.5) / len(durs)) if durs else 1.0
            out.append(
                {
                    **b,
                    "error_rate": (b["error_count"] / b["count"]) if b["count"] else 0.0,
                    "p50_ms": round(_percentile(durs, 50), 2),
                    "p75_ms": round(_percentile(durs, 75), 2),
                    "p95_ms": round(_percentile(durs, 95), 2),
                    "avg_ms": round(statistics.fmean(durs), 2) if durs else 0.0,
                    "apdex": round(apdex, 3),
                    "apdex_t_ms": apdex_t_ms,
                }
            )
        out.sort(key=lambda x: x["count"], reverse=True)
        return out

    async def traffic_timeline(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        where, params = self._analytics_where(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        cur = await self._execute(
            f"""
            SELECT SUBSTR(timestamp, 1, 16) AS bucket,
                   COUNT(*) AS count,
                   SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END)
                       AS errors_4xx,
                   SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors,
                   AVG(duration_ms) AS avg_ms,
                   SUM(request_size) AS bytes_in,
                   SUM(response_size) AS bytes_out
            FROM requests
            WHERE {where}
            GROUP BY bucket
            ORDER BY bucket
            """,
            params,
        )
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def consumer_stats(
        self,
        hours: int = 24,
        *,
        view: str = "individuals",
        group: str | None = None,
    ) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        if view == "groups":
            cur = await self._execute(
                f"""
                SELECT consumer_group AS group_name,
                       COUNT(*) AS count,
                       COUNT(DISTINCT consumer_id) AS unique_consumers,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
                       AVG(duration_ms) AS avg_ms
                FROM requests
                WHERE {INBOUND_FILTER}
                  AND timestamp >= %s
                  AND consumer_group IS NOT NULL AND consumer_group != ''
                GROUP BY consumer_group
                ORDER BY count DESC
                """,
                (since,),
            )
            rows = await cur.fetchall()
            await cur.close()
            return [dict(r) for r in rows]

        clauses = [INBOUND_FILTER, "timestamp >= %s", "consumer_id IS NOT NULL"]
        params: list[Any] = [since]
        if group:
            clauses.append("consumer_group = %s")
            params.append(group)
        where = " AND ".join(clauses)
        cur = await self._execute(
            f"""
            SELECT consumer_id, consumer_name, consumer_group,
                   COUNT(*) AS count,
                   SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
                   AVG(duration_ms) AS avg_ms,
                   MIN(timestamp) AS first_seen,
                   MAX(timestamp) AS last_seen
            FROM requests
            WHERE {where}
            GROUP BY consumer_id, consumer_name, consumer_group
            ORDER BY count DESC
            """,
            params,
        )
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def consumer_adoption(self, hours: int = 24) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(hours=hours)).isoformat()
        prior_since = (now - timedelta(hours=hours * 2)).isoformat()
        cur = await self._execute(
            f"""
            SELECT DISTINCT consumer_id FROM requests
            WHERE {INBOUND_FILTER} AND timestamp >= %s AND consumer_id IS NOT NULL
            """,
            (since,),
        )
        current = {r["consumer_id"] for r in await cur.fetchall()}
        await cur.close()
        cur = await self._execute(
            f"""
            SELECT DISTINCT consumer_id FROM requests
            WHERE {INBOUND_FILTER}
              AND timestamp >= %s AND timestamp < %s AND consumer_id IS NOT NULL
            """,
            (prior_since, since),
        )
        prior = {r["consumer_id"] for r in await cur.fetchall()}
        await cur.close()
        returning = current & prior
        new = current - prior
        return {
            "unique": len(current),
            "new": len(new),
            "returning": len(returning),
            "hours": hours,
        }

    async def status_error_stats(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> list[dict[str, Any]]:
        where, params = self._analytics_where(
            hours,
            consumer_id=consumer_id,
            consumer_group=consumer_group,
            extra=["status_code >= 400"],
        )
        cur = await self._execute(
            f"""
            SELECT status_code,
                   COUNT(*) AS count,
                   COUNT(DISTINCT consumer_id) AS affected_consumers,
                   MAX(timestamp) AS last_seen
            FROM requests
            WHERE {where}
            GROUP BY status_code
            ORDER BY count DESC
            """,
            params,
        )
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def performance_summary(
        self,
        hours: int = 24,
        *,
        apdex_t_ms: float = 500.0,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> dict[str, Any]:
        endpoints = await self.endpoint_stats(
            hours,
            consumer_id=consumer_id,
            consumer_group=consumer_group,
            apdex_t_ms=apdex_t_ms,
        )
        if not endpoints:
            return {
                "p50_ms": 0,
                "p75_ms": 0,
                "p95_ms": 0,
                "avg_ms": 0,
                "apdex": 1.0,
                "apdex_t_ms": apdex_t_ms,
                "request_count": 0,
            }
        total = sum(e["count"] for e in endpoints)
        where, params = self._analytics_where(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        cur = await self._execute(
            f"SELECT duration_ms FROM requests WHERE {where}", params
        )
        durs = [float(r["duration_ms"]) for r in await cur.fetchall()]
        await cur.close()
        satisfied = sum(1 for d in durs if d <= apdex_t_ms)
        tolerating = sum(1 for d in durs if apdex_t_ms < d <= 4 * apdex_t_ms)
        apdex = ((satisfied + tolerating * 0.5) / len(durs)) if durs else 1.0
        return {
            "p50_ms": round(_percentile(durs, 50), 2),
            "p75_ms": round(_percentile(durs, 75), 2),
            "p95_ms": round(_percentile(durs, 95), 2),
            "avg_ms": round(statistics.fmean(durs), 2) if durs else 0.0,
            "apdex": round(apdex, 3),
            "apdex_t_ms": apdex_t_ms,
            "request_count": total,
            "endpoints": endpoints,
        }

    async def traffic_summary(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
    ) -> dict[str, Any]:
        where, params = self._analytics_where(
            hours, consumer_id=consumer_id, consumer_group=consumer_group
        )
        cur = await self._execute(
            f"""
            SELECT COUNT(*) AS requests,
                   SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END)
                       AS errors_4xx,
                   SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors_5xx,
                   SUM(request_size) AS bytes_in,
                   SUM(response_size) AS bytes_out,
                   AVG(duration_ms) AS avg_ms
            FROM requests WHERE {where}
            """,
            params,
        )
        row = dict(await cur.fetchone())
        await cur.close()
        req = int(row.get("requests") or 0)
        err4 = int(row.get("errors_4xx") or 0)
        err5 = int(row.get("errors_5xx") or 0)
        rpm = round(req / max(hours * 60, 1), 3)
        return {
            **row,
            "requests": req,
            "errors_4xx": err4,
            "errors_5xx": err5,
            "error_rate": round((err4 + err5) / req, 4) if req else 0.0,
            "rpm": rpm,
            "hours": hours,
        }

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
    ) -> None:
        cur = await self._execute(
            """
            INSERT INTO uptime_checks(timestamp, kind, ok, latency_ms, status_code, message, path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                timestamp or datetime.now(timezone.utc).isoformat(),
                kind,
                1 if ok else 0,
                latency_ms,
                status_code,
                message,
                path,
            ),
        )
        await cur.close()
        await self.conn.commit()

    async def list_uptime_checks(
        self, hours: int = 24, *, kind: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= %s"]
        params: list[Any] = [since]
        if kind:
            clauses.append("kind = %s")
            params.append(kind)
        where = " AND ".join(clauses)
        params.append(limit)
        cur = await self._execute(
            f"""
            SELECT * FROM uptime_checks WHERE {where}
            ORDER BY timestamp DESC LIMIT %s
            """,
            params,
        )
        rows = await cur.fetchall()
        await cur.close()
        out = []
        for row in rows:
            d = dict(row)
            d["ok"] = bool(d["ok"])
            out.append(d)
        return out

    async def uptime_summary(self, hours: int = 24) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur = await self._execute(
            """
            SELECT kind,
                   COUNT(*) AS total,
                   SUM(ok) AS ok_count,
                   AVG(latency_ms) AS avg_latency_ms,
                   MAX(timestamp) AS last_check
            FROM uptime_checks
            WHERE timestamp >= %s
            GROUP BY kind
            """,
            (since,),
        )
        by_kind = {}
        for row in await cur.fetchall():
            d = dict(row)
            total = int(d["total"] or 0)
            ok_c = int(d["ok_count"] or 0)
            avg_lat = d["avg_latency_ms"]
            by_kind[d["kind"]] = {
                "total": total,
                "ok": ok_c,
                "fail": total - ok_c,
                "availability": round(ok_c / total, 4) if total else None,
                "avg_latency_ms": round(float(avg_lat or 0), 2),
                "last_check": d["last_check"],
            }
        await cur.close()
        cur = await self._execute(
            """
            SELECT SUBSTR(timestamp, 1, 16) AS bucket,
                   SUM(ok) AS ok_count,
                   COUNT(*) AS total
            FROM uptime_checks
            WHERE timestamp >= %s
            GROUP BY bucket
            ORDER BY bucket
            """,
            (since,),
        )
        timeline = [dict(r) for r in await cur.fetchall()]
        await cur.close()
        overall_total = sum(k["total"] for k in by_kind.values())
        overall_ok = sum(k["ok"] for k in by_kind.values())
        return {
            "hours": hours,
            "by_kind": by_kind,
            "availability": round(overall_ok / overall_total, 4) if overall_total else None,
            "timeline": timeline,
        }

    async def validation_heatmap(self, hours: int = 24) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur = await self._execute(
            f"""
            SELECT validation_errors, COALESCE(route, path) AS endpoint
            FROM requests
            WHERE {INBOUND_FILTER}
              AND timestamp >= %s AND status_code = 422 AND validation_errors IS NOT NULL
            """,
            (since,),
        )
        counts: dict[tuple[str, str, str], int] = {}
        for row in await cur.fetchall():
            errs = _json_loads(row["validation_errors"]) or []
            for err in errs:
                loc = ".".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", "")
                key = (row["endpoint"], loc, msg)
                counts[key] = counts.get(key, 0) + 1
        await cur.close()
        out = [
            {"endpoint": e, "field": f, "message": m, "count": c}
            for (e, f, m), c in counts.items()
        ]
        out.sort(key=lambda x: x["count"], reverse=True)
        return out

    async def error_groups(self, hours: int = 24) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur = await self._execute(
            f"""
            SELECT error_fingerprint, exception_type, COALESCE(route, path) AS endpoint,
                   COUNT(*) AS count, MAX(timestamp) AS last_seen, MAX(exception) AS sample
            FROM requests
            WHERE {INBOUND_FILTER}
              AND timestamp >= %s AND error_fingerprint IS NOT NULL
            GROUP BY error_fingerprint, exception_type, endpoint
            ORDER BY count DESC
            """,
            (since,),
        )
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def insert_trigger_history(self, record: TriggerHistoryRecord) -> None:
        cur = await self._execute(
            """
            INSERT INTO trigger_history(trigger_name, timestamp, success, message, fingerprint, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                record.trigger_name,
                record.timestamp,
                1 if record.success else 0,
                record.message,
                record.fingerprint,
                _json_dumps(record.details),
            ),
        )
        await cur.close()
        await self.conn.commit()

    async def list_trigger_history(self, limit: int = 100) -> list[dict[str, Any]]:
        cur = await self._execute(
            "SELECT * FROM trigger_history ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )
        out = []
        for row in await cur.fetchall():
            d = dict(row)
            d["success"] = bool(d["success"])
            d["details"] = _json_loads(d.get("details"))
            out.append(d)
        await cur.close()
        return out

    async def prune(self, max_requests: int, retention_hours: int) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
        cur = await self._execute("DELETE FROM requests WHERE timestamp < %s", (cutoff,))
        await cur.close()
        cur = await self._execute("SELECT COUNT(*) AS c FROM requests")
        row = await cur.fetchone()
        await cur.close()
        count = int(row["c"]) if row else 0
        if count > max_requests:
            excess = count - max_requests
            cur = await self._execute(
                """
                DELETE FROM requests WHERE id IN (
                    SELECT id FROM (
                        SELECT id FROM requests ORDER BY timestamp ASC LIMIT %s
                    ) AS doomed
                )
                """,
                (excess,),
            )
            await cur.close()
        cur = await self._execute(
            "DELETE FROM trigger_history WHERE timestamp < %s", (cutoff,)
        )
        await cur.close()
        cur = await self._execute(
            "DELETE FROM uptime_checks WHERE timestamp < %s", (cutoff,)
        )
        await cur.close()
        await self.conn.commit()

    async def counts(self) -> dict[str, int]:
        cur = await self._execute(
            f"SELECT COUNT(*) AS c FROM requests WHERE {INBOUND_FILTER}"
        )
        req = int((await cur.fetchone())["c"])
        await cur.close()
        cur = await self._execute(
            f"SELECT COUNT(*) AS c FROM requests WHERE {INBOUND_FILTER} AND status_code >= 500"
        )
        err = int((await cur.fetchone())["c"])
        await cur.close()
        cur = await self._execute(
            f"SELECT COUNT(*) AS c FROM requests WHERE {INBOUND_FILTER} AND status_code = 422"
        )
        v422 = int((await cur.fetchone())["c"])
        await cur.close()
        return {"requests": req, "errors_5xx": err, "validation_422": v422}

    async def observed_routes(self) -> set[str]:
        cur = await self._execute(
            f"""
            SELECT DISTINCT CONCAT(method, ' ', COALESCE(route, path)) AS ep
            FROM requests
            WHERE {INBOUND_FILTER}
            """
        )
        rows = await cur.fetchall()
        await cur.close()
        return {row["ep"] for row in rows}

    async def get_ui_config(self, key: str, default: Any = None) -> Any:
        cur = await self._execute(
            "SELECT value FROM ui_config WHERE `key` = %s", (key,)
        )
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return default
        return _json_loads(row["value"])

    async def set_ui_config(self, key: str, value: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cur = await self._execute(
            """
            INSERT INTO ui_config(`key`, value, updated_at) VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                value = VALUES(value),
                updated_at = VALUES(updated_at)
            """,
            (key, _json_dumps(value), now),
        )
        await cur.close()
        await self.conn.commit()

    async def get_all_ui_config(self) -> dict[str, Any]:
        cur = await self._execute("SELECT `key`, value, updated_at FROM ui_config")
        out: dict[str, Any] = {}
        for row in await cur.fetchall():
            out[row["key"]] = {
                "value": _json_loads(row["value"]),
                "updated_at": row["updated_at"],
            }
        await cur.close()
        return out
