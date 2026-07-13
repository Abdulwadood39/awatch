# Consumers

Tag **who** made a request for debugging and adoption analytics.

Apitally-style fields:

- `identifier` — required (user / client id)
- `name` — optional display name
- `group` — optional group (e.g. company / tenant)

## Tag in a route

```python
from fastapi import Depends, Request
from monitorit import awatch

@app.get("/items")
def items(request: Request, user=Depends(get_user)):
    awatch.set_consumer(
        request,
        identifier=user.id,
        name=user.email,
        group=user.company_id,
    )
    return []
```

Call `set_consumer()` as early as you know the identity (middleware or dependency also works).

## Dashboard

**Consumers** tab:

- Toggle **Groups | Individuals**
- See unique / new / returning adoption
- Drill group → individuals → request logs

There is **no** Settings UI for consumer fingerprints — use code only.
