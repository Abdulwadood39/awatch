"""Exclude path matching tests."""

from awatch.privacy.mask import PrivacyFilter, path_matches_exclude


def test_exact_and_prefix():
    assert path_matches_exclude("/auth/login", "/auth")
    assert path_matches_exclude("/auth", "/auth")
    assert not path_matches_exclude("/oauth", "/auth")


def test_glob():
    assert path_matches_exclude("/users/42/password", "/users/*/password")
    assert path_matches_exclude("/private/a/b", "/private/*")


def test_regex():
    assert path_matches_exclude("/internal/secret", r"^/internal/.*$")


def test_privacy_filter_excludes():
    p = PrivacyFilter(exclude_paths=["/secret", "/pii/*"], dashboard_path="/__awatch")
    assert p.should_exclude("/secret")
    assert p.should_exclude("/secret/key")
    assert p.should_exclude("/pii/email")
    assert p.should_exclude("/__awatch/api/overview")
    assert p.should_exclude("/.well-known/appspecific/com.chrome.devtools.json")
    assert not p.should_exclude("/api/public")


def test_well_known_and_health_defaults():
    from awatch.core.constants import DEFAULT_EXCLUDE_PATHS

    p = PrivacyFilter(exclude_paths=list(DEFAULT_EXCLUDE_PATHS), dashboard_path="/__awatch")
    assert p.should_exclude("/health")
    assert p.should_exclude("/.well-known/appspecific/com.chrome.devtools.json")


def test_set_exclude_paths_merges_runtime():
    p = PrivacyFilter(exclude_paths=["/health"], dashboard_path="/__awatch")
    p.set_exclude_paths(["/health", "/auth/login", "/auth/login"])
    assert p.exclude_paths == ["/health", "/auth/login"]
    assert p.should_exclude("/auth/login")
