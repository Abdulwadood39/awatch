"""Storage backend factory."""

from __future__ import annotations

from typing import Any

from monitorit.awatch.storage.base import StorageProtocol


def create_storage(config: Any) -> StorageProtocol:
    """Create a storage backend from AWatchConfig (or compatible object)."""
    kind = str(getattr(config, "storage", "sqlite") or "sqlite").lower().strip()

    if kind == "sqlite":
        from monitorit.awatch.storage.sqlite import SQLiteStorage

        return SQLiteStorage(config.resolved_db_path())

    if kind in {"postgres", "postgresql"}:
        url = config.resolved_database_url()
        if not url:
            raise ValueError(
                "postgres storage requires database_url or postgres_url "
                "(e.g. postgresql://user:pass@localhost:5432/awatch)"
            )
        from monitorit.awatch.storage.postgres import PostgresStorage

        return PostgresStorage(url)

    if kind == "mysql":
        url = config.resolved_database_url()
        if not url:
            raise ValueError(
                "mysql storage requires database_url "
                "(e.g. mysql://user:pass@localhost:3306/awatch)"
            )
        from monitorit.awatch.storage.mysql import MySQLStorage

        return MySQLStorage(url)

    raise ValueError(f"Unknown storage backend: {kind!r} (expected sqlite|postgres|mysql)")
