"""Privacy unit tests."""

from awatch.privacy.mask import PrivacyFilter


def test_mask_authorization_header():
    p = PrivacyFilter(mask_headers=[r"authorization"], mask_query_params=[], mask_body_fields=[])
    out = p.mask_headers({"Authorization": "Bearer secret", "Accept": "application/json"})
    assert out["Authorization"] == "***"
    assert out["Accept"] == "application/json"
    assert p.report()["headers"] == 1


def test_mask_body_password():
    p = PrivacyFilter(mask_headers=[], mask_query_params=[], mask_body_fields=[r"password"])
    masked = p.mask_body(b'{"password":"hunter2","ok":true}')
    assert "hunter2" not in masked
    assert "***" in masked


def test_exclude_dashboard_and_health():
    p = PrivacyFilter(exclude_paths=["/health", "/docs"], dashboard_path="/__awatch")
    assert p.should_exclude("/health")
    assert p.should_exclude("/__awatch")
    assert p.should_exclude("/__awatch/api/overview")
    assert not p.should_exclude("/api/items")
