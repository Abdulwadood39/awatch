# Categories (traffic labels)

Optional labels for slicing traffic by path, header, or JSON body. **Code-only** — not editable in Settings.

```python
from monitorit import awatch

awatch.AWatch(
    app,
    env="dev",
    categories=[
        awatch.CategoryRule(name="admin", when=awatch.path_prefix("/admin"), priority=10),
        awatch.CategoryRule(name="partner", when=awatch.header_equals("X-Partner-Id", "*")),
    ],
)
```

Load rules from your DB:

```python
from monitorit import awatch

awatch.AWatch(
    app,
    category_loader=awatch.sqlalchemy_loader(
        engine,
        "SELECT name, rule_type, rule_value, priority FROM awatch_categories WHERE active = 1",
    ),
)
```

Demo:

```bash
uvicorn examples.with_categories:app --reload
```
