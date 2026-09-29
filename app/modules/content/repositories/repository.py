from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models.models import Post


class ContentRepository:
	def __init__(self, session: AsyncSession) -> None:
		self._session = session

	@staticmethod
	def _payload(post: Post) -> dict[str, Any]:
		return {field: getattr(post, field) for field in (
			"id", "author_id", "community_id", "title", "body", "created_at", "updated_at", "is_deleted",
		)}

	async def create(self, data: dict[str, Any]) -> dict[str, Any]:
		post = Post(**data)
		self._session.add(post)
		await self._session.flush()
		return self._payload(post)

	async def _get_post(self, post_id: UUID) -> Post | None:
		statement = select(Post).where(Post.id == post_id, Post.is_deleted.is_(False))
		return await self._session.scalar(statement)

	async def get_by_id(self, post_id: UUID) -> dict[str, Any] | None:
		post = await self._get_post(post_id)
		return self._payload(post) if post is not None else None

	async def get_feed(self, community_ids: Sequence[UUID], limit: int, offset: int) -> list[dict[str, Any]]:
		if not community_ids:
			return []

		statement = (
			select(Post)
			.where(
				Post.is_deleted.is_(False),
				Post.community_id.in_(list(community_ids)),
			)
			.order_by(Post.created_at.desc(), Post.id.desc())
			.limit(limit)
			.offset(offset)
		)
		return [self._payload(post) for post in (await self._session.scalars(statement)).all()]

	async def get_user_posts(self, author_id: UUID, community_ids: Sequence[UUID]) -> list[dict[str, Any]]:
		if not community_ids:
			return []

		statement = (
			select(Post)
			.where(
				Post.is_deleted.is_(False),
				Post.author_id == author_id,
				Post.community_id.in_(list(community_ids)),
			)
			.order_by(Post.created_at.desc(), Post.id.desc())
		)
		return [self._payload(post) for post in (await self._session.scalars(statement)).all()]

	async def get_community_posts(self, community_id: UUID, limit: int, offset: int) -> list[dict[str, Any]]:
		statement = (
			select(Post)
			.where(
				Post.is_deleted.is_(False),
				Post.community_id == community_id,
			)
			.order_by(Post.created_at.desc(), Post.id.desc())
			.limit(limit)
			.offset(offset)
		)
		return [self._payload(post) for post in (await self._session.scalars(statement)).all()]

	async def soft_delete(self, post_id: UUID) -> bool:
		post = await self._get_post(post_id)
		if post is None:
			return False

		post.is_deleted = True
		await self._session.flush()
		return True


__all__ = ["ContentRepository"]
