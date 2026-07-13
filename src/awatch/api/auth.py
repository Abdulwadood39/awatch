"""API auth helpers."""

from __future__ import annotations

import secrets
from typing import Any, Callable

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)
_api_key = APIKeyHeader(name="X-AWatch-Token", auto_error=False)


def build_auth_dependency(
    auth_token: str | None,
    auth_dependency: Callable[..., Any] | None = None,
    *,
    env: str = "dev",
) -> Callable[..., Any] | None:
    if auth_dependency is not None:
        return auth_dependency

    if not auth_token:
        if env.lower() in {"prod", "production"}:
            raise RuntimeError("auth required in production")
        return None

    async def _verify(
        bearer: HTTPAuthorizationCredentials | None = Security(_bearer),
        api_key: str | None = Security(_api_key),
    ) -> bool:
        provided = None
        if bearer and bearer.credentials:
            provided = bearer.credentials
        elif api_key:
            provided = api_key
        if provided is None or not secrets.compare_digest(provided, auth_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return True

    return _verify
