from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

import pytest

from app.modules.social_graph.models.models import FriendRequest, FriendRequestStatus
from app.modules.social_graph.repositories.repository import SocialGraphRepository
from app.modules.users.models.models import User
from app.modules.users.repositories.repository import UserRepository
from app.modules.users.services.service import UserService


class ScalarSession:
	def __init__(self, row: Any) -> None:
		self.row = row

	async def scalar(self, statement: Any) -> Any:
		return self.row


@pytest.mark.asyncio
async def test_user_service_receives_snapshot_without_exposing_credentials() -> None:
	user_id = uuid4()
	now = datetime.now(timezone.utc)
	user = User(id=user_id, username="user", email="user@example.com",
		hashed_password="secret", is_active=True, created_at=now)
	repo = UserRepository(cast(Any, ScalarSession(user)))

	account = await repo.get_by_id(user_id)
	assert isinstance(account, dict)
	assert account["hashed_password"] == "secret"
	assert (await UserService(repo).get_user(user_id)) == {
		"id": user_id, "username": "user", "email": "user@example.com",
		"is_active": True, "created_at": now,
	}


@pytest.mark.asyncio
async def test_repository_converts_orm_enum_before_service_boundary() -> None:
	request = FriendRequest(id=uuid4(), requester_id=uuid4(), receiver_id=uuid4(),
		status=FriendRequestStatus.PENDING, created_at=datetime.now(timezone.utc),
		updated_at=datetime.now(timezone.utc))
	repo = SocialGraphRepository(cast(Any, ScalarSession(request)))

	payload = await repo.get_request_by_id(request.id)
	assert isinstance(payload, dict)
	assert payload["status"] == "pending"
	assert payload["requester_id"] == request.requester_id
