"""SQLite storage backend with WAL mode."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from awatch.storage.migrations import SCHEMA_SQL, SCHEMA_VERSION
from awatch.storage.models import RequestRecord, TriggerHistoryRecord


def _json_dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, default=str)


def _json_loads(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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


class SQLiteStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None
        self.ready = False
        self.last_error: str | None = None

    async def setup(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.execute(
            "INSERT OR REPLACE INTO awatch_meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        await self._conn.commit()
        self.ready = True

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            self.ready = False

    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._conn:
            raise RuntimeError("SQLiteStorage not initialized")
        return self._conn

    async def ping(self) -> bool:
        try:
            await self.conn.execute("SELECT 1")
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return False

    async def insert_request(self, record: RequestRecord) -> None:
        r = record
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO requests (
                request_id, timestamp, method, path, route, status_code, duration_ms,
                client_ip, user_agent, request_size, response_size,
                query_params, request_headers, response_headers, request_body, response_body,
                exception, exception_type, consumer_id, consumer_name, consumer_group,
                categories, logs, spans, validation_errors, release, error_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        await self.conn.commit()

    def _row_to_dict(self, row: aiosqlite.Row) -> dict[str, Any]:
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
            d[key] = _json_loads(d.get(key))
        return d

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
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if hours is not None:
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            clauses.append("timestamp >= ?")
            params.append(since)
        if status_code is not None:
            clauses.append("status_code = ?")
            params.append(status_code)
        if status_class == "4xx":
            clauses.append("status_code >= 400 AND status_code < 500")
        elif status_class == "5xx":
            clauses.append("status_code >= 500")
        elif status_class == "2xx":
            clauses.append("status_code >= 200 AND status_code < 300")
        if method:
            clauses.append("method = ?")
            params.append(method.upper())
        if path_contains:
            clauses.append("path LIKE ?")
            params.append(f"%{path_contains}%")
        if consumer_id:
            clauses.append("consumer_id = ?")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = ?")
            params.append(consumer_group)
        if category:
            clauses.append("categories LIKE ?")
            params.append(f'%"{category}"%')
        if min_duration_ms is not None:
            clauses.append("duration_ms >= ?")
            params.append(min_duration_ms)
        if client_ip:
            clauses.append("client_ip = ?")
            params.append(client_ip)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        cur = await self.conn.execute(
            f"SELECT * FROM requests {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        cur = await self.conn.execute(
            "SELECT * FROM requests WHERE request_id = ?", (request_id,)
        )
        row = await cur.fetchone()
        return self._row_to_dict(row) if row else None

    async def endpoint_stats(
        self,
        hours: int = 24,
        *,
        consumer_id: str | None = None,
        consumer_group: str | None = None,
        apdex_t_ms: float = 500.0,
    ) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= ?"]
        params: list[Any] = [since]
        if consumer_id:
            clauses.append("consumer_id = ?")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = ?")
            params.append(consumer_group)
        where = " AND ".join(clauses)
        cur = await self.conn.execute(
            f"""
            SELECT method, COALESCE(route, path) AS endpoint, status_code, duration_ms,
                   request_size, response_size
            FROM requests WHERE {where}
            """,
            params,
        )
        rows = await cur.fetchall()
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
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= ?"]
        params: list[Any] = [since]
        if consumer_id:
            clauses.append("consumer_id = ?")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = ?")
            params.append(consumer_group)
        where = " AND ".join(clauses)
        cur = await self.conn.execute(
            f"""
            SELECT substr(timestamp, 1, 16) AS bucket,
                   COUNT(*) AS count,
                   SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) AS errors_4xx,
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
            cur = await self.conn.execute(
                """
                SELECT consumer_group AS group_name,
                       COUNT(*) AS count,
                       COUNT(DISTINCT consumer_id) AS unique_consumers,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
                       AVG(duration_ms) AS avg_ms
                FROM requests
                WHERE timestamp >= ? AND consumer_group IS NOT NULL AND consumer_group != ''
                GROUP BY consumer_group
                ORDER BY count DESC
                """,
                (since,),
            )
            return [dict(r) for r in await cur.fetchall()]

        clauses = ["timestamp >= ?", "consumer_id IS NOT NULL"]
        params: list[Any] = [since]
        if group:
            clauses.append("consumer_group = ?")
            params.append(group)
        where = " AND ".join(clauses)
        cur = await self.conn.execute(
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
        return [dict(r) for r in await cur.fetchall()]

    async def consumer_adoption(self, hours: int = 24) -> dict[str, Any]:
        """Unique / new / returning consumers in the window vs prior window."""
        now = datetime.now(timezone.utc)
        since = (now - timedelta(hours=hours)).isoformat()
        prior_since = (now - timedelta(hours=hours * 2)).isoformat()
        cur = await self.conn.execute(
            """
            SELECT DISTINCT consumer_id FROM requests
            WHERE timestamp >= ? AND consumer_id IS NOT NULL
            """,
            (since,),
        )
        current = {r["consumer_id"] for r in await cur.fetchall()}
        cur = await self.conn.execute(
            """
            SELECT DISTINCT consumer_id FROM requests
            WHERE timestamp >= ? AND timestamp < ? AND consumer_id IS NOT NULL
            """,
            (prior_since, since),
        )
        prior = {r["consumer_id"] for r in await cur.fetchall()}
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
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= ?", "status_code >= 400"]
        params: list[Any] = [since]
        if consumer_id:
            clauses.append("consumer_id = ?")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = ?")
            params.append(consumer_group)
        where = " AND ".join(clauses)
        cur = await self.conn.execute(
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
        return [dict(r) for r in await cur.fetchall()]

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
        # Weighted percentiles approximation from endpoint avgs is weak;
        # re-query raw durations for global percentiles.
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= ?"]
        params: list[Any] = [since]
        if consumer_id:
            clauses.append("consumer_id = ?")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = ?")
            params.append(consumer_group)
        where = " AND ".join(clauses)
        cur = await self.conn.execute(
            f"SELECT duration_ms FROM requests WHERE {where}", params
        )
        durs = [float(r["duration_ms"]) for r in await cur.fetchall()]
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
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= ?"]
        params: list[Any] = [since]
        if consumer_id:
            clauses.append("consumer_id = ?")
            params.append(consumer_id)
        if consumer_group:
            clauses.append("consumer_group = ?")
            params.append(consumer_group)
        where = " AND ".join(clauses)
        cur = await self.conn.execute(
            f"""
            SELECT COUNT(*) AS requests,
                   SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) AS errors_4xx,
                   SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors_5xx,
                   SUM(request_size) AS bytes_in,
                   SUM(response_size) AS bytes_out,
                   AVG(duration_ms) AS avg_ms
            FROM requests WHERE {where}
            """,
            params,
        )
        row = dict(await cur.fetchone())
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
        await self.conn.execute(
            """
            INSERT INTO uptime_checks(timestamp, kind, ok, latency_ms, status_code, message, path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
        await self.conn.commit()

    async def list_uptime_checks(
        self, hours: int = 24, *, kind: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses = ["timestamp >= ?"]
        params: list[Any] = [since]
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = " AND ".join(clauses)
        params.append(limit)
        cur = await self.conn.execute(
            f"""
            SELECT * FROM uptime_checks WHERE {where}
            ORDER BY timestamp DESC LIMIT ?
            """,
            params,
        )
        out = []
        for row in await cur.fetchall():
            d = dict(row)
            d["ok"] = bool(d["ok"])
            out.append(d)
        return out

    async def uptime_summary(self, hours: int = 24) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur = await self.conn.execute(
            """
            SELECT kind,
                   COUNT(*) AS total,
                   SUM(ok) AS ok_count,
                   AVG(latency_ms) AS avg_latency_ms,
                   MAX(timestamp) AS last_check
            FROM uptime_checks
            WHERE timestamp >= ?
            GROUP BY kind
            """,
            (since,),
        )
        by_kind = {}
        for row in await cur.fetchall():
            d = dict(row)
            total = int(d["total"] or 0)
            ok_c = int(d["ok_count"] or 0)
            by_kind[d["kind"]] = {
                "total": total,
                "ok": ok_c,
                "fail": total - ok_c,
                "availability": round(ok_c / total, 4) if total else None,
                "avg_latency_ms": round(float(d["avg_latency_ms"] or 0), 2),
                "last_check": d["last_check"],
            }
        # Minute buckets for timeline
        cur = await self.conn.execute(
            """
            SELECT substr(timestamp, 1, 16) AS bucket,
                   SUM(ok) AS ok_count,
                   COUNT(*) AS total
            FROM uptime_checks
            WHERE timestamp >= ?
            GROUP BY bucket
            ORDER BY bucket
            """,
            (since,),
        )
        timeline = [dict(r) for r in await cur.fetchall()]
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
        cur = await self.conn.execute(
            """
            SELECT validation_errors, COALESCE(route, path) AS endpoint
            FROM requests
            WHERE timestamp >= ? AND status_code = 422 AND validation_errors IS NOT NULL
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
        out = [
            {"endpoint": e, "field": f, "message": m, "count": c}
            for (e, f, m), c in counts.items()
        ]
        out.sort(key=lambda x: x["count"], reverse=True)
        return out

    async def error_groups(self, hours: int = 24) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur = await self.conn.execute(
            """
            SELECT error_fingerprint, exception_type, COALESCE(route, path) AS endpoint,
                   COUNT(*) AS count, MAX(timestamp) AS last_seen, MAX(exception) AS sample
            FROM requests
            WHERE timestamp >= ? AND error_fingerprint IS NOT NULL
            GROUP BY error_fingerprint, exception_type, endpoint
            ORDER BY count DESC
            """,
            (since,),
        )
        return [dict(r) for r in await cur.fetchall()]

    async def insert_trigger_history(self, record: TriggerHistoryRecord) -> None:
        await self.conn.execute(
            """
            INSERT INTO trigger_history(trigger_name, timestamp, success, message, fingerprint, details)
            VALUES (?, ?, ?, ?, ?, ?)
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
        await self.conn.commit()

    async def list_trigger_history(self, limit: int = 100) -> list[dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT * FROM trigger_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        out = []
        for row in await cur.fetchall():
            d = dict(row)
            d["success"] = bool(d["success"])
            d["details"] = _json_loads(d.get("details"))
            out.append(d)
        return out

    async def prune(self, max_requests: int, retention_hours: int) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
        await self.conn.execute("DELETE FROM requests WHERE timestamp < ?", (cutoff,))
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM requests")
        row = await cur.fetchone()
        count = int(row["c"]) if row else 0
        if count > max_requests:
            excess = count - max_requests
            await self.conn.execute(
                """
                DELETE FROM requests WHERE id IN (
                    SELECT id FROM requests ORDER BY timestamp ASC LIMIT ?
                )
                """,
                (excess,),
            )
        await self.conn.execute("DELETE FROM trigger_history WHERE timestamp < ?", (cutoff,))
        await self.conn.execute("DELETE FROM uptime_checks WHERE timestamp < ?", (cutoff,))
        await self.conn.commit()

    async def counts(self) -> dict[str, int]:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM requests")
        req = int((await cur.fetchone())["c"])
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status_code >= 500"
        )
        err = int((await cur.fetchone())["c"])
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status_code = 422"
        )
        v422 = int((await cur.fetchone())["c"])
        return {"requests": req, "errors_5xx": err, "validation_422": v422}

    async def observed_routes(self) -> set[str]:
        cur = await self.conn.execute(
            "SELECT DISTINCT method || ' ' || COALESCE(route, path) AS ep FROM requests"
        )
        return {row["ep"] for row in await cur.fetchall()}

    # --- UI configuration persistence ---

    async def get_ui_config(self, key: str, default: Any = None) -> Any:
        cur = await self.conn.execute(
            "SELECT value FROM ui_config WHERE key = ?", (key,)
        )
        row = await cur.fetchone()
        if not row:
            return default
        return _json_loads(row["value"])

    async def set_ui_config(self, key: str, value: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.conn.execute(
            """
            INSERT INTO ui_config(key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, _json_dumps(value), now),
        )
        await self.conn.commit()

    async def get_all_ui_config(self) -> dict[str, Any]:
        cur = await self.conn.execute("SELECT key, value, updated_at FROM ui_config")
        out: dict[str, Any] = {}
        for row in await cur.fetchall():
            out[row["key"]] = {
                "value": _json_loads(row["value"]),
                "updated_at": row["updated_at"],
            }
        return out
