from __future__ import annotations

from collections.abc import MutableMapping
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from pydantic import ValidationError
from starlette import status
from starlette.requests import Request

from app.main import app
from app.modules.admins.services.service import AdminService
from app.modules.content.api.user_routes import _get_optional_current_user
from app.modules.notifications.api.router import notifications_websocket
from app.modules.users.services.service import UserService
from app.shared.auth.dependencies import bearer_scheme, get_current_user, require_permission
from app.shared.auth.jwt import Audience, JWTClaims, SystemJWTClaims, create_access_token, create_refresh_token, decode_token
from app.shared.config.settings import settings
from app.shared.dependencies.content_deps import get_content_service
from app.shared.exceptions.handlers import ForbiddenError, UnauthorizedError


class FakeUserRepository:
    def __init__(self) -> None:
        self.lookups = 0

    async def get_by_id(self, user_id: Any) -> Any:
        self.lookups += 1
        return SimpleNamespace(id=user_id, is_active=True)


class FakeAdminRepository:
    def __init__(self) -> None:
        self.lookups = 0

    async def get_user_by_id(self, user_id: Any) -> Any:
        self.lookups += 1
        return SimpleNamespace(id=user_id, is_active=True)

    async def get_user_permissions(self, user_id: Any) -> list[str]:
        return ["content.posts.delete"]


def signed(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_user_and_system_tokens_have_separate_strict_claims() -> None:
    user_id = uuid4()
    user_pair = UserService(cast(Any, FakeUserRepository()))._token_pair(user_id)
    system_pair = AdminService(cast(Any, FakeAdminRepository()))._token_pair(
        user_id, ["content.posts.delete"]
    )

    for pair, audience, access_permissions in (
        (user_pair, "user", []),
        (system_pair, "system", ["content.posts.delete"]),
    ):
        assert pair["token_type"] == "bearer"
        for token_type, permissions in (("access", access_permissions), ("refresh", [])):
            claims = decode_token(pair[f"{token_type}_token"])
            assert set(claims) == {"aud", "sub", "permissions", "iat", "exp", "jti", "token_type"}
            assert claims["aud"] == audience
            assert claims["sub"] == str(user_id)
            assert claims["token_type"] == token_type
            assert claims["permissions"] == permissions
            assert claims["exp"] > claims["iat"]
            assert claims["jti"]


@pytest.mark.parametrize("audience", ["user", "system"])
@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.pop("aud"),
        lambda p: p.update(aud="other"),
        lambda p: p.update(aud=["user", "system"]),
        lambda p: p.pop("permissions"),
        lambda p: p.update(permissions="content.posts.delete"),
        lambda p: p.update(permissions=[1]),
        lambda p: p.update(permissions=[""]),
        lambda p: p.update(sub=123),
        lambda p: p.pop("iat"),
        lambda p: p.update(iat="1"),
        lambda p: p.pop("exp"),
        lambda p: p.update(exp="tomorrow"),
        lambda p: p.pop("jti"),
        lambda p: p.update(token_type="other"),
        lambda p: p.update(tenant_id="unknown"),
        lambda p: p.update(system_permissions=[]),
    ],
)
def test_decoder_rejects_missing_extra_and_mistyped_claims(audience: str, change: Any) -> None:
    payload = decode_token(create_access_token(uuid4(), audience=cast(Audience, audience), permissions=[]))
    change(payload)
    with pytest.raises(UnauthorizedError):
        decode_token(signed(payload))


def test_user_permissions_must_be_empty_even_when_signed() -> None:
    payload = decode_token(create_access_token(uuid4(), audience="user", permissions=[]))
    payload["permissions"] = ["content.posts.delete"]
    with pytest.raises(UnauthorizedError):
        decode_token(signed(payload))
    with pytest.raises(ValidationError):
        create_access_token(uuid4(), audience="user", permissions=["content.posts.delete"])


def test_claim_models_reject_the_opposite_audience() -> None:
    user = decode_token(create_access_token(uuid4(), audience="user", permissions=[]))
    system = decode_token(create_access_token(uuid4(), audience="system", permissions=[]))
    with pytest.raises(ValidationError):
        JWTClaims.model_validate(system)
    with pytest.raises(ValidationError):
        SystemJWTClaims.model_validate(user)


def test_system_refresh_cannot_carry_permissions() -> None:
    payload = decode_token(create_refresh_token(uuid4(), audience="system"))
    payload["permissions"] = ["content.posts.delete"]
    with pytest.raises(UnauthorizedError):
        decode_token(signed(payload))


def test_issuance_rejects_malformed_claims_before_signing() -> None:
    for subject in ("", 123):
        with pytest.raises(ValidationError):
            create_access_token(cast(Any, subject), audience="system", permissions=[])
    with pytest.raises(ValidationError):
        create_access_token(uuid4(), audience="system", permissions=cast(Any, "content.posts.delete"))
    with pytest.raises(ValueError):
        create_refresh_token(uuid4(), audience=cast(Any, "elsewhere"))


@pytest.mark.asyncio
async def test_bearer_authentication_requires_access_token() -> None:
    token = create_access_token(uuid4(), audience="user", permissions=[])
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    bearer_credentials = await bearer_scheme(request)
    assert bearer_credentials is not None
    assert bearer_credentials.scheme == "Bearer"
    assert bearer_credentials.credentials == token
    assert (await get_current_user(bearer_credentials))["aud"] == "user"
    assert await bearer_scheme(Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"authorization", f"Basic {token}".encode())]})) is None
    with pytest.raises(UnauthorizedError):
        await get_current_user(None)
    with pytest.raises(UnauthorizedError):
        await get_current_user(credentials(create_refresh_token(uuid4(), audience="user")))
    with pytest.raises(UnauthorizedError):
        await get_current_user(credentials(token + "invalid"))


@pytest.mark.asyncio
async def test_audience_guard_rejects_system_token_on_user_routes() -> None:
    system = await get_current_user(credentials(create_access_token(uuid4(), audience="system", permissions=[])))
    user = await get_current_user(credentials(create_access_token(uuid4(), audience="user", permissions=[])))
    assert await require_permission(audience="user")(user) == user
    with pytest.raises(UnauthorizedError):
        await require_permission(audience="user")(system)
    with pytest.raises(UnauthorizedError):
        await _get_optional_current_user(credentials(create_access_token(uuid4(), audience="system", permissions=[])))
    assert await _get_optional_current_user(None) is None


@pytest.mark.asyncio
async def test_system_permission_denial_and_wrong_audience() -> None:
    permission = "content.posts.delete"
    dependency = require_permission(audience="system", permission=permission)
    system = await get_current_user(credentials(create_access_token(uuid4(), audience="system", permissions=[])))
    user = await get_current_user(credentials(create_access_token(uuid4(), audience="user", permissions=[])))
    with pytest.raises(ForbiddenError):
        await dependency(system)
    with pytest.raises(UnauthorizedError):
        await dependency(user)
    authorized = await get_current_user(credentials(create_access_token(uuid4(), audience="system", permissions=[permission])))
    assert await dependency(authorized) == authorized


@pytest.mark.asyncio
async def test_refresh_rejects_cross_audience_and_access_before_lookup() -> None:
    user_repo = FakeUserRepository()
    admin_repo = FakeAdminRepository()
    user_service = UserService(cast(Any, user_repo))
    admin_service = AdminService(cast(Any, admin_repo))
    user_refresh = create_refresh_token(uuid4(), audience="user")
    system_refresh = create_refresh_token(uuid4(), audience="system")
    with pytest.raises(UnauthorizedError):
        await admin_service.refresh_tokens(refresh_token=user_refresh)
    with pytest.raises(UnauthorizedError):
        await user_service.refresh_tokens(refresh_token=system_refresh)
    with pytest.raises(UnauthorizedError):
        await user_service.refresh_tokens(refresh_token=create_access_token(uuid4(), audience="user", permissions=[]))
    assert user_repo.lookups == admin_repo.lookups == 0
    assert decode_token((await user_service.refresh_tokens(refresh_token=user_refresh))["access_token"])["aud"] == "user"
    system_pair = await admin_service.refresh_tokens(refresh_token=system_refresh)
    assert decode_token(system_pair["access_token"])["permissions"] == ["content.posts.delete"]
    assert decode_token(system_pair["refresh_token"])["permissions"] == []
    assert user_repo.lookups == admin_repo.lookups == 1


async def request_status(method: str, path: str, token: str) -> int:
    statuses: list[int] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: MutableMapping[str, Any]) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "server": ("testserver", 80),
            "client": ("testclient", 12345),
        },
        receive,
        send,
    )
    return statuses[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/users/me"),
        ("GET", f"/api/v1/users/{uuid4()}"),
        ("GET", "/api/v1/social/friends"),
        ("GET", "/api/v1/communities/roles"),
        ("GET", "/api/v1/notifications"),
        ("DELETE", f"/api/v1/posts/{uuid4()}"),
        ("GET", "/api/v1/posts"),
    ],
)
async def test_user_routes_reject_system_bearer(method: str, path: str) -> None:
    token = create_access_token(uuid4(), audience="system", permissions=["content.posts.delete"])
    assert await request_status(method, path, token) == 401


@pytest.mark.asyncio
async def test_system_routes_reject_user_bearer_and_deny_missing_permission() -> None:
    post_route = f"/api/v1/admin/posts/{uuid4()}"
    user_token = create_access_token(uuid4(), audience="user", permissions=[])
    system_token = create_access_token(uuid4(), audience="system", permissions=[])
    assert await request_status("DELETE", post_route, user_token) == 401
    assert await request_status("DELETE", post_route, system_token) == 403
    assert await request_status("GET", "/api/v1/admins/roles", user_token) == 401
    assert await request_status("GET", "/api/v1/admins/roles", system_token) == 403


@pytest.mark.asyncio
async def test_post_deletion_routes_pass_only_their_intended_authorization() -> None:
    calls: list[tuple[Any, Any, bool]] = []

    class FakeContentService:
        async def delete_post(self, post_id: Any, requester_id: Any, *, can_delete_any: bool) -> None:
            calls.append((post_id, requester_id, can_delete_any))

    app.dependency_overrides[get_content_service] = lambda: FakeContentService()
    post_id = uuid4()
    user_id = uuid4()
    system_id = uuid4()
    try:
        assert await request_status(
            "DELETE", f"/api/v1/posts/{post_id}",
            create_access_token(user_id, audience="user", permissions=[]),
        ) == 204
        assert await request_status(
            "DELETE", f"/api/v1/admin/posts/{post_id}",
            create_access_token(system_id, audience="system", permissions=["content.posts.delete"]),
        ) == 204
    finally:
        app.dependency_overrides.pop(get_content_service, None)
    assert calls == [(post_id, str(user_id), False), (post_id, str(system_id), True)]


@pytest.mark.asyncio
async def test_notifications_websocket_rejects_system_audience() -> None:
    closed: list[int] = []

    class FakeWebSocket:
        async def close(self, *, code: int) -> None:
            closed.append(code)

        async def accept(self) -> None:
            pytest.fail("Wrong-audience WebSocket was accepted")

    token = create_access_token(uuid4(), audience="system", permissions=[])
    await notifications_websocket(cast(Any, FakeWebSocket()), token, cast(Any, object()))
    assert closed == [status.WS_1008_POLICY_VIOLATION]
