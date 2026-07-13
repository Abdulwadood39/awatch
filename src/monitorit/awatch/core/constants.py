"""Shared constants for awatch."""

DEFAULT_DASHBOARD_PATH = "/__awatch"
DEFAULT_DB_FILENAME = "awatch.db"
MASKED = "***"
DEFAULT_EXCLUDE_PATHS = (
    "/health",
    "/healthz",
    "/ready",
    "/readyz",
    "/livez",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/metrics",
    "/.well-known/*",
)

# Header / query / body field name patterns (case-insensitive substring match)
DEFAULT_MASK_HEADERS = (
    r"authorization",
    r"cookie",
    r"set-cookie",
    r"x-api-key",
    r"api[-_]?key",
    r"x-auth",
    r"proxy-authorization",
)
DEFAULT_MASK_QUERY = (
    r"api[-_]?key",
    r"token",
    r"secret",
    r"password",
    r"access[-_]?token",
    r"refresh[-_]?token",
)
DEFAULT_MASK_BODY_FIELDS = (
    r"password",
    r"passwd",
    r"secret",
    r"token",
    r"api[-_]?key",
    r"access[-_]?token",
    r"refresh[-_]?token",
    r"credit[-_]?card",
    r"card[-_]?number",
    r"cvv",
    r"ssn",
)

MAX_BODY_BYTES = 64_000
REQUEST_ID_HEADER = "X-Request-ID"
