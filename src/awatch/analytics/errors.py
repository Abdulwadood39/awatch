"""Error fingerprinting."""

from __future__ import annotations

import hashlib
import re


def fingerprint_exception(
    exception_type: str | None,
    endpoint: str | None,
    exception_text: str | None,
) -> str | None:
    if not exception_type:
        return None
    # Normalize message: drop memory addresses / line numbers noise lightly
    msg = ""
    if exception_text:
        lines = exception_text.strip().splitlines()
        msg = lines[-1] if lines else exception_text
        msg = re.sub(r"0x[0-9a-fA-F]+", "0x?", msg)
        msg = re.sub(r"\d+", "#", msg)
    raw = f"{exception_type}|{endpoint or ''}|{msg}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]
