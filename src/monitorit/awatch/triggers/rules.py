"""Trigger rule definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from monitorit.awatch.triggers.conditions import _parse_window


@dataclass
class Trigger:
    name: str
    when: Any
    then: Any  # Action | list[Action]
    cooldown: str = "5m"

    def actions(self) -> list[Any]:
        if isinstance(self.then, (list, tuple)):
            return list(self.then)
        return [self.then]

    def cooldown_seconds(self) -> float:
        return _parse_window(self.cooldown)
