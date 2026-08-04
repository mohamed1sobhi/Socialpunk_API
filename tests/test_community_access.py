from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.modules.communities.models.models import CommunityVisibility
from app.modules.communities.repositories.repository import CommunityRepository
from app.modules.communities.services.service import CommunityService


class FakeCommunityRepository:
	def __init__(self) -> None:
		self.communities: dict[UUID, SimpleNamespace] = {}
		self.members: set[tuple[UUID, UUID]] = set()
		self.accessible_ids: list[UUID] = []
		self.last_accessible_viewer: UUID | None = None

	async def get_by_id(self, community_id: UUID):
		return self.communities.get(community_id)

	async def get_member(self, user_id: UUID, community_id: UUID):
		if (user_id, community_id) in self.members:
			return SimpleNamespace(id=uuid4())
		return None

	async def list_accessible_ids(self, viewer_id: UUID | None) -> list[UUID]:
		self.last_accessible_viewer = viewer_id
		return self.accessible_ids


class FakeUsersClient:
	pass


class FakeSession:
	def __init__(self) -> None:
		self.added: Any | None = None

	def add(self, value: Any) -> None:
		self.added = value

	async def flush(self) -> None:
		return None


@pytest.mark.asyncio
async def test_public_community_is_visible_anonymously() -> None:
	repo = FakeCommunityRepository()
	community_id = uuid4()
	repo.communities[community_id] = SimpleNamespace(
		id=community_id,
		owner_id=uuid4(),
		visibility="public",
	)

	access = await CommunityService(cast(Any, repo), cast(Any, FakeUsersClient())).get_access(
		community_id,
		None,
	)

	assert access == {"community_id": community_id, "can_view": True, "is_member": False}


@pytest.mark.asyncio
async def test_private_community_requires_owner_or_member() -> None:
	repo = FakeCommunityRepository()
	community_id = uuid4()
	owner_id = uuid4()
	member_id = uuid4()
	nonmember_id = uuid4()
	repo.communities[community_id] = SimpleNamespace(
		id=community_id,
		owner_id=owner_id,
		visibility="private",
	)
	repo.members.add((member_id, community_id))
	service = CommunityService(cast(Any, repo), cast(Any, FakeUsersClient()))

	assert (await service.get_access(community_id, None))["can_view"] is False
	assert (await service.get_access(community_id, nonmember_id))["can_view"] is False
	assert (await service.get_access(community_id, member_id))["can_view"] is True
	assert (await service.get_access(community_id, owner_id))["can_view"] is True


@pytest.mark.asyncio
async def test_accessible_ids_support_anonymous_and_authenticated_viewers() -> None:
	repo = FakeCommunityRepository()
	repo.accessible_ids = [uuid4(), uuid4()]
	service = CommunityService(cast(Any, repo), cast(Any, FakeUsersClient()))

	assert await service.list_accessible_community_ids(None) == {"community_ids": repo.accessible_ids}
	assert repo.last_accessible_viewer is None

	viewer_id = uuid4()
	assert await service.list_accessible_community_ids(viewer_id) == {"community_ids": repo.accessible_ids}
	assert repo.last_accessible_viewer == viewer_id


@pytest.mark.asyncio
async def test_repository_normalizes_api_visibility_to_lowercase_enum_values() -> None:
	session = FakeSession()
	repo = CommunityRepository(cast(Any, session))

	community = await repo.create_community(
		{
			"id": uuid4(),
			"name": "Community",
			"description": None,
			"visibility": "public",
			"owner_id": uuid4(),
		}
	)

	assert community.visibility is CommunityVisibility.PUBLIC
	assert CommunityVisibility.PUBLIC.value == "public"
