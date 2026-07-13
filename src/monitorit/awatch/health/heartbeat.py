"""Silent API heartbeat tracking."""

from __future__ import annotations

import time


class HeartbeatTracker:
    def __init__(self) -> None:
        self.last_request_at: float | None = None

    def beat(self) -> None:
        self.last_request_at = time.time()

    def silent_for(self, seconds: float) -> bool:
        if self.last_request_at is None:
            return False
        return (time.time() - self.last_request_at) >= seconds

    def age_seconds(self) -> float | None:
        if self.last_request_at is None:
            return None
        return time.time() - self.last_request_at
