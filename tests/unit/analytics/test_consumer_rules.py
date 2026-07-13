"""Consumer fingerprint extract rules."""

from awatch.analytics.consumer_rules import (
    ConsumerExtractor,
    ConsumerRule,
    FieldRef,
    compile_consumer_defs,
    extract_request_value,
)


def test_extract_header_query_json():
    assert (
        extract_request_value("header", "X-API-Key", headers={"x-api-key": "abc"})
        == "abc"
    )
    assert extract_request_value("query", "tenant", query={"tenant": "acme"}) == "acme"
    assert (
        extract_request_value(
            "json",
            "org.id",
            body=b'{"org":{"id":"42"},"plan":"pro"}',
        )
        == "42"
    )


def test_resolve_fingerprint_group_and_identifier():
    extractor = ConsumerExtractor(
        rules=[
            ConsumerRule(
                name="company_user",
                method="POST",
                path="/payments/*",
                identifier=FieldRef("json", "user_id"),
                group=FieldRef("json", "company_id"),
                name_field=FieldRef("json", "email"),
            )
        ]
    )
    got = extractor.resolve(
        method="POST",
        path="/payments/charge",
        body=b'{"company_id":"acme","user_id":"u1","email":"a@acme.com","amount":10}',
    )
    assert got["identifier"] == "u1"
    assert got["group"] == "acme"
    assert got["name"] == "a@acme.com"
    assert got["rule"] == "company_user"


def test_missing_identifier_skips_rule():
    extractor = ConsumerExtractor(
        rules=[
            ConsumerRule(
                name="needs_user",
                identifier=FieldRef("header", "X-User-Id"),
                group=FieldRef("header", "X-Company-Id"),
            )
        ]
    )
    assert (
        extractor.resolve(
            method="GET",
            path="/items",
            headers={"X-Company-Id": "c1"},
        )
        is None
    )


def test_compile_legacy_filters_and_new_shape():
    rules = compile_consumer_defs(
        [
            {
                "name": "legacy",
                "filters": [
                    {"source": "query", "key": "uid"},
                    {"source": "query", "key": "cid"},
                ],
            },
            {
                "name": "new",
                "identifier": {"source": "json", "key": "user_id"},
                "group": {"source": "json", "key": "company_id"},
            },
        ]
    )
    assert len(rules) == 2
    assert rules[0].identifier.key == "uid"
    assert rules[0].group and rules[0].group.key == "cid"
    assert rules[1].identifier.key == "user_id"
