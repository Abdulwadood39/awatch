"""Sampling decisions for request logging."""

from __future__ import annotations

import random


def should_sample_request(
    *,
    status_code: int,
    duration_ms: float,
    slow_threshold_ms: float,
    success_sample_rate: float,
) -> bool:
    """Always keep errors, validation failures, and slow requests; sample the rest."""
    if status_code >= 400:
        return True
    if duration_ms >= slow_threshold_ms:
        return True
    if success_sample_rate >= 1.0:
        return True
    if success_sample_rate <= 0.0:
        return False
    return random.random() < success_sample_rate
