"""Validation + fingerprint tests."""

from monitorit.awatch.analytics.errors import fingerprint_exception
from monitorit.awatch.analytics.validation import extract_validation_errors


def test_extract_validation_errors():
    body = b'{"detail":[{"loc":["body","email"],"msg":"field required","type":"missing"}]}'
    errs = extract_validation_errors(body)
    assert errs[0]["loc"] == ["body", "email"]
    assert errs[0]["msg"] == "field required"


def test_fingerprint_stable():
    a = fingerprint_exception("ValueError", "GET /x", "ValueError: bad 123 at 0xabc")
    b = fingerprint_exception("ValueError", "GET /x", "ValueError: bad 999 at 0xdef")
    assert a == b
    assert a is not None
