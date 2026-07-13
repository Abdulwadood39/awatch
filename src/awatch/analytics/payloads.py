"""Payload size helpers."""

from __future__ import annotations


def classify_size(nbytes: int) -> str:
    if nbytes < 1024:
        return "lt_1kb"
    if nbytes < 100 * 1024:
        return "lt_100kb"
    if nbytes < 1024 * 1024:
        return "lt_1mb"
    return "gte_1mb"
