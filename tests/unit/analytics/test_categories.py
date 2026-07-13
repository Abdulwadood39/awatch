"""Category rule tests."""

import pytest

from monitorit.awatch.analytics.categories import CategoryEngine, CategoryRule, header_equals, path_prefix


@pytest.mark.asyncio
async def test_category_engine_matches():
    engine = CategoryEngine(
        [
            CategoryRule(name="admin", when=path_prefix("/admin"), priority=10),
            CategoryRule(name="partner", when=header_equals("X-Partner-Id", "*"), priority=1),
        ]
    )
    cats = await engine.evaluate(
        method="GET",
        path="/admin/users",
        headers={"X-Partner-Id": "acme"},
        query={},
        body=None,
        consumer=None,
    )
    assert "admin" in cats
    assert "partner" in cats


@pytest.mark.asyncio
async def test_single_label_stops_at_first():
    engine = CategoryEngine(
        [
            CategoryRule(name="admin", when=path_prefix("/admin"), priority=10),
            CategoryRule(name="all", when=path_prefix("/"), priority=1),
        ],
        multi_label=False,
    )
    cats = await engine.evaluate(
        method="GET", path="/admin/x", headers={}, query={}, body=None, consumer=None
    )
    assert cats == ["admin"]
