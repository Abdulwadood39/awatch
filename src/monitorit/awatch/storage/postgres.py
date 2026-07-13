"""Optional Postgres storage (requires awatch[postgres])."""

from __future__ import annotations

from typing import Any


class PostgresStorage:
    def __init__(self, url: str) -> None:
        self.url = url
        raise NotImplementedError(
            "Postgres storage requires awatch[postgres]. "
            "Use storage='sqlite' for now, or contribute a PR."
        )

    async def setup(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        return None
