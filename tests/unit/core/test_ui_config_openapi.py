"""OpenAPI inventory parsing for Settings dropdowns."""

from monitorit.awatch.core.ui_config import aggregate_openapi_keys, parse_openapi_paths


def test_parse_openapi_extracts_params_and_body_fields():
    schema = {
        "paths": {
            "/payments/charge": {
                "post": {
                    "summary": "Charge",
                    "tags": ["payments"],
                    "parameters": [
                        {"name": "X-Partner-Id", "in": "header", "schema": {"type": "string"}},
                        {"name": "dry_run", "in": "query", "schema": {"type": "boolean"}},
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "amount": {"type": "number"},
                                        "plan": {"type": "string"},
                                        "meta": {
                                            "type": "object",
                                            "properties": {"source": {"type": "string"}},
                                        },
                                    },
                                }
                            }
                        }
                    },
                }
            },
            "/items/{item_id}": {
                "get": {
                    "parameters": [
                        {"name": "item_id", "in": "path", "schema": {"type": "string"}},
                    ],
                    "summary": "Get item",
                }
            },
        }
    }
    rows = parse_openapi_paths(schema)
    charge = next(r for r in rows if r["path"] == "/payments/charge")
    assert charge["method"] == "POST"
    assert charge["headers"] == ["X-Partner-Id"]
    assert charge["query"] == ["dry_run"]
    assert "amount" in charge["body_fields"]
    assert "plan" in charge["body_fields"]
    assert "meta.source" in charge["body_fields"]

    item = next(r for r in rows if r["path"] == "/items/{item_id}")
    assert item["glob_path"] == "/items/*"
    assert item["path_params"] == ["item_id"]

    keys = aggregate_openapi_keys(rows)
    assert "X-Partner-Id" in keys["headers"]
    assert "plan" in keys["body_fields"]
    assert "/payments/charge" in keys["paths"]


def test_parse_openapi_resolves_schema_ref():
    schema = {
        "components": {
            "schemas": {
                "ChargeBody": {
                    "type": "object",
                    "properties": {"currency": {"type": "string"}},
                }
            }
        },
        "paths": {
            "/pay": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChargeBody"}
                            }
                        }
                    }
                }
            }
        },
    }
    rows = parse_openapi_paths(schema)
    assert rows[0]["body_fields"] == ["currency"]
