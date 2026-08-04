from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.modules.content.schemas.api_schemas import CreatePostRequest, PostResponse
from app.modules.content.services.service import ContentService
from app.shared.exceptions.handlers import ForbiddenError, ValidationError


def make_post(*, community_id: UUID, author_id: UUID | None = None) -> SimpleNamespace:
	now = datetime.now(timezone.utc)
	return SimpleNamespace(
		id=uuid4(),
		author_id=author_id or uuid4(),
		community_id=community_id,
		title=None,
		body="Post body",
		created_at=now,
		updated_at=now,
		is_deleted=False,
	)


class FakeContentRepository:
	def __init__(self) -> None:
		self.posts: dict[UUID, SimpleNamespace] = {}
		self.created_data: dict[str, Any] | None = None
		self.feed_call: tuple[list[UUID], int, int] | None = None

	async def create(self, data: dict[str, Any]):
		self.created_data = data
		post = make_post(community_id=data["community_id"], author_id=data["author_id"])
		post.id = data["id"]
		post.title = data["title"]
		post.body = data["body"]
		self.posts[post.id] = post
		return post

	async def get_by_id(self, post_id: UUID):
		return self.posts.get(post_id)

	async def get_feed(self, community_ids: list[UUID], limit: int, offset: int):
		self.feed_call = (community_ids, limit, offset)
		return [post for post in self.posts.values() if post.community_id in community_ids]

	async def get_user_posts(self, author_id: UUID, community_ids: list[UUID]):
		return [
			post
			for post in self.posts.values()
			if post.author_id == author_id and post.community_id in community_ids
		]

	async def get_community_posts(self, community_id: UUID, limit: int, offset: int):
		return [post for post in self.posts.values() if post.community_id == community_id]

	async def soft_delete(self, post_id: UUID) -> bool:
		return post_id in self.posts


class FakeCommunitiesClient:
	def __init__(self) -> None:
		self.members: set[tuple[UUID, UUID]] = set()
		self.viewable_ids: set[UUID] = set()
		self.accessible_ids: list[UUID] = []

	async def is_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
		normalized_community_id = UUID(community_id) if isinstance(community_id, str) else community_id
		return {
			"community_id": normalized_community_id,
			"user_id": normalized_user_id,
			"is_member": (normalized_user_id, normalized_community_id) in self.members,
		}

	async def get_access(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		normalized_community_id = UUID(community_id) if isinstance(community_id, str) else community_id
		normalized_viewer_id = UUID(viewer_id) if isinstance(viewer_id, str) else viewer_id
		return {
			"community_id": normalized_community_id,
			"can_view": normalized_community_id in self.viewable_ids,
			"is_member": normalized_viewer_id is not None
			and (normalized_viewer_id, normalized_community_id) in self.members,
		}

	async def list_accessible_community_ids(
		self,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		return {"community_ids": self.accessible_ids}


@pytest.mark.asyncio
async def test_create_post_requires_community_membership() -> None:
	repo = FakeContentRepository()
	communities = FakeCommunitiesClient()
	service = ContentService(repo, communities)
	author_id = uuid4()
	community_id = uuid4()

	with pytest.raises(ForbiddenError):
		await service.create_post(author_id, {"community_id": community_id, "body": "Body"})

	communities.members.add((author_id, community_id))
	post = await service.create_post(author_id, {"community_id": community_id, "body": " Body "})

	assert post["community_id"] == community_id
	assert post["body"] == "Body"
	assert "visibility" not in post
	assert repo.created_data is not None
	assert "visibility" not in repo.created_data


@pytest.mark.asyncio
async def test_create_post_rejects_missing_community() -> None:
	service = ContentService(FakeContentRepository(), FakeCommunitiesClient())

	with pytest.raises(ValidationError, match="Community id is required"):
		await service.create_post(uuid4(), {"body": "Body"})


@pytest.mark.asyncio
async def test_direct_post_read_uses_community_access() -> None:
	repo = FakeContentRepository()
	communities = FakeCommunitiesClient()
	community_id = uuid4()
	post = make_post(community_id=community_id)
	repo.posts[post.id] = post
	service = ContentService(repo, communities)

	with pytest.raises(ForbiddenError):
		await service.get_post(post.id, None)

	communities.viewable_ids.add(community_id)
	assert (await service.get_post(post.id, None))["id"] == post.id


@pytest.mark.asyncio
async def test_feed_filters_by_accessible_communities_before_pagination() -> None:
	repo = FakeContentRepository()
	communities = FakeCommunitiesClient()
	accessible_id = uuid4()
	hidden_id = uuid4()
	communities.accessible_ids = [accessible_id]
	visible_post = make_post(community_id=accessible_id)
	hidden_post = make_post(community_id=hidden_id)
	repo.posts = {visible_post.id: visible_post, hidden_post.id: hidden_post}

	payload = await ContentService(repo, communities).list_feed(None, limit=10, offset=2)

	assert repo.feed_call == ([accessible_id], 10, 2)
	assert [post["id"] for post in payload["posts"]] == [visible_post.id]


def test_post_api_contract_requires_community_and_forbids_visibility() -> None:
	with pytest.raises(PydanticValidationError):
		CreatePostRequest.model_validate({"body": "Body"})

	with pytest.raises(PydanticValidationError):
		CreatePostRequest.model_validate(
			{"community_id": uuid4(), "body": "Body", "visibility": "public"}
		)

	post = make_post(community_id=uuid4())
	payload = PostResponse.model_validate(post).model_dump()
	assert "visibility" not in payload
