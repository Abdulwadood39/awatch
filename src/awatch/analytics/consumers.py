"""Consumer helpers."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from awatch.core.context import ConsumerInfo, set_consumer_ctx


def set_consumer(
    request: Request | Any,
    identifier: str,
    name: str | None = None,
    group: str | None = None,
) -> None:
    """Associate the current request with an API consumer."""
    info = ConsumerInfo(identifier=str(identifier), name=name, group=group)
    payload = info.to_dict()
    set_consumer_ctx(info)
    # Stash on request.state and ASGI scope (scope survives ASGI middleware reliably)
    try:
        request.state.awatch_consumer = payload
    except Exception:  # noqa: BLE001
        pass
    try:
        request.scope["awatch_consumer"] = payload
    except Exception:  # noqa: BLE001
        pass
