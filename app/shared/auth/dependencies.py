from __future__ import annotations

from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.shared.auth.jwt import decode_token
from app.shared.exceptions.handlers import ForbiddenError, UnauthorizedError


# Swagger can point to only one OAuth2 password endpoint, but bearer tokens from
# both login surfaces are accepted because validation is claim-based only.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login", auto_error=False)


def _require_string_claim(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise UnauthorizedError("Invalid token payload")
    return value


def _validate_permissions_claim(payload: dict[str, Any]) -> None:
    if "system_permissions" not in payload:
        return
    permissions = payload.get("system_permissions")
    if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
        raise UnauthorizedError("Invalid token payload")


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    if not token:
        raise UnauthorizedError("Not authenticated")

    payload = decode_token(token)
    _require_string_claim(payload, "sub")
    token_type = _require_string_claim(payload, "token_type")
    _validate_permissions_claim(payload)

    if token_type != "access":
        raise UnauthorizedError("Access token required")

    return payload


def require_system_permission(permission_name: str):
    async def dependency(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        permissions = current_user.get("system_permissions", [])
        if permission_name not in permissions:
            raise ForbiddenError(f"Missing required permission: {permission_name}")
        return current_user

    return dependency


__all__ = ["get_current_user", "oauth2_scheme", "require_system_permission"]
