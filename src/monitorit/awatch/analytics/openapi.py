"""OpenAPI route inventory and drift detection."""

from __future__ import annotations

from typing import Any


def collect_registered_routes(app: Any) -> set[str]:
    routes: set[str] = set()
    for route in getattr(app, "routes", []):
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.add(f"{method} {path}")
    return routes


def compute_drift(registered: set[str], observed: set[str]) -> dict[str, list[str]]:
    dead = sorted(registered - observed)
    undocumented = sorted(observed - registered)
    return {
        "registered": sorted(registered),
        "observed": sorted(observed),
        "dead": dead,  # documented but never called
        "undocumented": undocumented,  # called but not in OpenAPI/routes
    }
