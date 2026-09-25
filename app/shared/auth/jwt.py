from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.shared.config.settings import settings
from app.shared.exceptions.handlers import UnauthorizedError


Audience = Literal["user", "system"]


class JWTClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    aud: Literal["user"]
    sub: str = Field(min_length=1)
    permissions: list[str]
    iat: int
    exp: int
    jti: str = Field(min_length=1)
    token_type: Literal["access", "refresh"]

    @field_validator("permissions")
    @classmethod
    def empty_user_permissions(cls, permissions: list[str]) -> list[str]:
        if permissions:
            raise ValueError("User tokens cannot carry system permissions")
        return permissions


class SystemJWTClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    aud: Literal["system"]
    sub: str = Field(min_length=1)
    permissions: list[str]
    iat: int
    exp: int
    jti: str = Field(min_length=1)
    token_type: Literal["access", "refresh"]

    @field_validator("permissions")
    @classmethod
    def nonempty_permission_names(cls, permissions: list[str]) -> list[str]:
        if any(not permission for permission in permissions):
            raise ValueError("Permissions must be non-empty strings")
        return permissions

    @model_validator(mode="after")
    def refresh_has_no_permissions(self) -> SystemJWTClaims:
        if self.token_type == "refresh" and self.permissions:
            raise ValueError("Refresh tokens cannot carry permissions")
        return self


password_hasher = PasswordHasher()


def _claims_model(audience: object) -> type[JWTClaims] | type[SystemJWTClaims]:
    if audience == "user":
        return JWTClaims
    if audience == "system":
        return SystemJWTClaims
    raise ValueError("Unknown token audience")


def _encode_token(
    subject: UUID | str,
    *,
    audience: Audience,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    permissions: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    claims = _claims_model(audience).model_validate(
        {
            "aud": audience,
            "sub": str(subject) if isinstance(subject, UUID) else subject,
            "permissions": permissions,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
            "jti": str(uuid4()),
            "token_type": token_type,
        }
    )
    return jwt.encode(claims.model_dump(), settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: UUID | str, *, audience: Audience, permissions: list[str]) -> str:
    return _encode_token(
        subject,
        audience=audience,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        permissions=permissions,
    )


def create_refresh_token(subject: UUID | str, *, audience: Audience) -> str:
    return _encode_token(
        subject,
        audience=audience,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        permissions=[],
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
        if not isinstance(payload, dict):
            raise UnauthorizedError("Invalid token payload")
        model = _claims_model(payload.get("aud"))
        return model.model_validate(payload).model_dump()
    except (JWTError, ValidationError, ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


def hash_password(plain: str) -> str:
    return password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(hashed, plain)
    except (InvalidHashError, VerificationError, VerifyMismatchError, TypeError, ValueError):
        return False


__all__ = [
    "JWTClaims",
    "SystemJWTClaims",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
