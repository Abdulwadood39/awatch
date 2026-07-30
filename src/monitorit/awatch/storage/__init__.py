"""Storage package."""

from monitorit.awatch.storage.base import StorageProtocol
from monitorit.awatch.storage.factory import create_storage
from monitorit.awatch.storage.models import RequestRecord, TriggerHistoryRecord
from monitorit.awatch.storage.queue import WriteQueue
from monitorit.awatch.storage.sqlite import SQLiteStorage

__all__ = [
    "RequestRecord",
    "TriggerHistoryRecord",
    "WriteQueue",
    "StorageProtocol",
    "SQLiteStorage",
    "PostgresStorage",
    "MySQLStorage",
    "create_storage",
]


def __getattr__(name: str):
    if name == "PostgresStorage":
        from monitorit.awatch.storage.postgres import PostgresStorage

        return PostgresStorage
    if name == "MySQLStorage":
        from monitorit.awatch.storage.mysql import MySQLStorage

        return MySQLStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
