from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest
from jose import jwt

from app.modules.users.services.service import UserService
from app.shared.auth.dependencies import get_current_user, require_system_permission
from app.shared.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.shared.config.settings import settings
from app.shared.exceptions.handlers import ForbiddenError, UnauthorizedError


class FakeUserRepository:
	pass


def test_normal_user_tokens_omit_system_permissions() -> None:
	user_id = uuid4()
	pair = UserService(cast(Any, FakeUserRepository()))._token_pair(user_id)

	assert "system_permissions" not in decode_token(pair["access_token"])
	assert "system_permissions" not in decode_token(pair["refresh_token"])


def test_admin_access_token_keeps_explicit_permissions() -> None:
	token = create_access_token(uuid4(), ["content.posts.delete"])

	assert decode_token(token)["system_permissions"] == ["content.posts.delete"]
	assert "system_permissions" not in decode_token(create_refresh_token(uuid4()))


@pytest.mark.asyncio
async def test_missing_permission_claim_is_accepted_without_mutating_payload() -> None:
	payload = await get_current_user(create_access_token(uuid4()))

	assert "system_permissions" not in payload


@pytest.mark.asyncio
async def test_missing_permission_claim_fails_closed_for_system_routes() -> None:
	dependency = require_system_permission("content.posts.delete")

	with pytest.raises(ForbiddenError):
		await dependency({"sub": str(uuid4()), "token_type": "access"})


@pytest.mark.asyncio
@pytest.mark.parametrize("permissions", ["content.posts.delete", None])
async def test_malformed_permission_claim_is_rejected(permissions: object) -> None:
	token = jwt.encode(
		{
			"sub": str(uuid4()),
			"token_type": "access",
			"system_permissions": permissions,
		},
		settings.SECRET_KEY,
		algorithm=settings.ALGORITHM,
	)

	with pytest.raises(UnauthorizedError):
		await get_current_user(token)
