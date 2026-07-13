# Categories (traffic labels)

Optional labels for slicing traffic by path, header, or JSON body. **Code-only** — not editable in Settings.

```python
from awatch import AWatch, CategoryRule, header_equals, path_prefix

AWatch(
    app,
    env="dev",
    categories=[
        CategoryRule(name="admin", when=path_prefix("/admin"), priority=10),
        CategoryRule(name="partner", when=header_equals("X-Partner-Id", "*")),
    ],
)
```

Load rules from your DB:

```python
from awatch import sqlalchemy_loader

AWatch(
    app,
    category_loader=sqlalchemy_loader(
        engine,
        "SELECT name, rule_type, rule_value, priority FROM awatch_categories WHERE active = 1",
    ),
)
```

Demo:

```bash
uvicorn examples.with_categories:app --reload
```
