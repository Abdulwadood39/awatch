"""Scrubbing report for the dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monitorit.awatch.privacy.mask import PrivacyFilter


def build_scrubbing_report(privacy: PrivacyFilter) -> dict:
    counts = privacy.report()
    return {
        "masked_headers": counts.get("headers", 0),
        "masked_query_params": counts.get("query", 0),
        "masked_body_fields": counts.get("body_fields", 0),
        "note": "Counts are cumulative since process start. Bodies/headers are off by default.",
    }
