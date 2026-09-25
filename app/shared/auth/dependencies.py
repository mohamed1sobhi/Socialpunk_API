from __future__ import annotations

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.shared.auth.jwt import Audience, decode_token
from app.shared.exceptions.handlers import ForbiddenError, UnauthorizedError


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Not authenticated")

    payload = decode_token(credentials.credentials)
    if payload["token_type"] != "access":
        raise UnauthorizedError("Access token required")
    return payload


def require_permission(*, audience: Audience, permission: str | None = None):
    async def dependency(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if current_user["aud"] != audience:
            raise UnauthorizedError("Wrong token audience")
        if permission is not None and permission not in current_user["permissions"]:
            raise ForbiddenError(f"Missing required permission: {permission}")
        return current_user

    return dependency


__all__ = ["bearer_scheme", "get_current_user", "require_permission"]
