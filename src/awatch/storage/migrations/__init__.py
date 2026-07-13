"""SQLite schema migration."""

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS awatch_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ui_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    route TEXT,
    status_code INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    client_ip TEXT,
    user_agent TEXT,
    request_size INTEGER DEFAULT 0,
    response_size INTEGER DEFAULT 0,
    query_params TEXT,
    request_headers TEXT,
    response_headers TEXT,
    request_body TEXT,
    response_body TEXT,
    exception TEXT,
    exception_type TEXT,
    consumer_id TEXT,
    consumer_name TEXT,
    consumer_group TEXT,
    categories TEXT,
    logs TEXT,
    spans TEXT,
    validation_errors TEXT,
    release TEXT,
    error_fingerprint TEXT
);

CREATE INDEX IF NOT EXISTS idx_requests_timestamp ON requests(timestamp);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status_code);
CREATE INDEX IF NOT EXISTS idx_requests_route ON requests(route);
CREATE INDEX IF NOT EXISTS idx_requests_consumer ON requests(consumer_id);
CREATE INDEX IF NOT EXISTS idx_requests_consumer_group ON requests(consumer_group);
CREATE INDEX IF NOT EXISTS idx_requests_fingerprint ON requests(error_fingerprint);

CREATE TABLE IF NOT EXISTS trigger_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL,
    message TEXT,
    fingerprint TEXT,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_trigger_ts ON trigger_history(timestamp);

CREATE TABLE IF NOT EXISTS app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    timestamp TEXT NOT NULL,
    level TEXT,
    logger TEXT,
    message TEXT
);

CREATE TABLE IF NOT EXISTS uptime_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    ok INTEGER NOT NULL,
    latency_ms REAL,
    status_code INTEGER,
    message TEXT,
    path TEXT
);

CREATE INDEX IF NOT EXISTS idx_uptime_ts ON uptime_checks(timestamp);
CREATE INDEX IF NOT EXISTS idx_uptime_kind ON uptime_checks(kind);
"""
