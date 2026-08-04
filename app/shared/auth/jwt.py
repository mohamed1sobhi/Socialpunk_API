from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.shared.config.settings import settings
from app.shared.exceptions.handlers import UnauthorizedError


password_hasher = PasswordHasher()


def _validate_subject(subject: UUID | str) -> str:
    if isinstance(subject, UUID):
        return str(subject)
    if isinstance(subject, str) and subject:
        return subject
    raise ValueError("Token subject must be a non-empty string or UUID")


def _validate_permissions(system_permissions: Sequence[str] | None) -> list[str]:
    if isinstance(system_permissions, str):
        raise ValueError("System permissions must be a sequence of non-empty strings")
    permissions = list(system_permissions or [])
    if any(not isinstance(permission, str) or not permission for permission in permissions):
        raise ValueError("System permissions must be a sequence of non-empty strings")
    return permissions


def _encode_token(
    subject: UUID | str,
    token_type: str,
    expires_delta: timedelta,
    system_permissions: Sequence[str] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    issued_at = int(now.timestamp())
    expires_at = int((now + expires_delta).timestamp())
    payload: dict[str, Any] = {
        "sub": _validate_subject(subject),
        "token_type": token_type,
        "iat": issued_at,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    if system_permissions is not None:
        payload["system_permissions"] = _validate_permissions(system_permissions)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    subject: UUID | str,
    system_permissions: Sequence[str] | None = None,
) -> str:
    return _encode_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        system_permissions=system_permissions,
    )


def create_refresh_token(subject: UUID | str) -> str:
    return _encode_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    if not isinstance(payload, dict):
        raise UnauthorizedError("Invalid token payload")

    return payload


def hash_password(plain: str) -> str:
    return password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(hashed, plain)
    except (InvalidHashError, VerificationError, VerifyMismatchError, TypeError, ValueError):
        return False


__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
