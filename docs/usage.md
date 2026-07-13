# Usage

## Minimal integration

```python
from fastapi import FastAPI
from awatch import AWatch

app = FastAPI()
AWatch(app, env="dev")
```

Run your app as usual:

```bash
uvicorn your_module:app --reload
```

Open the dashboard:

[http://127.0.0.1:8000/__awatch](http://127.0.0.1:8000/__awatch)

## Demo apps in this repo

```bash
pip install -e ".[dev]"

uvicorn examples.basic_app:app --reload
# http://127.0.0.1:8000/__awatch

uvicorn examples.with_categories:app --reload
uvicorn examples.with_triggers:app --reload
```

Generate traffic against the basic demo:

```bash
curl http://127.0.0.1:8000/
curl -X POST http://127.0.0.1:8000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"gadget","price":9.5}'
curl http://127.0.0.1:8000/boom
```

Then open **Request logs** and click a row to inspect status, latency, bodies (if enabled), and logs.

## Production-shaped setup

```python
import os
from fastapi import FastAPI
from awatch import AWatch

app = FastAPI()

AWatch(
    app,
    env="prod",
    auth_token=os.environ["AWATCH_TOKEN"],
    allow_ui_config=False,  # lock Settings writes
    db_path="/var/lib/awatch/awatch.db",
)
```

`env="prod"` **requires** `auth_token` or `auth_dependency`.

### Unlock the dashboard in a browser

- Query param (saved in browser storage):  
  `http://127.0.0.1:8000/__awatch/?token=YOUR_TOKEN`
- Or open `/__awatch` and paste the token in the Unlock dialog

API clients can send:

```http
Authorization: Bearer YOUR_TOKEN
# or
X-AWatch-Token: YOUR_TOKEN
```

## Tag who made the request

```python
from fastapi import Depends, Request
from awatch import set_consumer

@app.get("/items")
def items(request: Request, user=Depends(get_user)):
    set_consumer(
        request,
        identifier=user.id,
        name=user.email,
        group=user.company_id,
    )
    return []
```

See [Consumers](consumers.md), [Categories](categories.md), and [Alerts](alerts.md) for deeper patterns.
