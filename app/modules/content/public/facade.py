from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.content.schemas.public_schemas.requests import (
	ContentCommunityPostsLookupRequest,
	ContentPostLookupRequest,
	ContentUserPostsLookupRequest,
)


class ContentServiceProtocol(Protocol):
	async def get_post(self, post_id: UUID | str, viewer_id: UUID | str | None) -> dict[str, Any]: ...
	async def list_user_posts(self, author_id: UUID | str, viewer_id: UUID | str | None) -> dict[str, Any]: ...
	async def list_community_posts(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None,
		*,
		limit: int,
		offset: int,
	) -> dict[str, Any]: ...


class ContentFacade:
	def __init__(self, service: ContentServiceProtocol) -> None:
		self._service = service

	async def get_post(self, post_id: UUID | str, viewer_id: UUID | str | None = None) -> dict[str, Any]:
		request = ContentPostLookupRequest.model_validate(
			{"post_id": post_id, "viewer_id": viewer_id}
		)
		return await self._service.get_post(request.post_id, request.viewer_id)

	async def list_user_posts(
		self,
		author_id: UUID | str,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		request = ContentUserPostsLookupRequest.model_validate(
			{"author_id": author_id, "viewer_id": viewer_id}
		)
		return await self._service.list_user_posts(request.author_id, request.viewer_id)

	async def list_community_posts(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None = None,
		*,
		limit: int = 50,
		offset: int = 0,
	) -> dict[str, Any]:
		request = ContentCommunityPostsLookupRequest.model_validate(
			{
				"community_id": community_id,
				"viewer_id": viewer_id,
				"limit": limit,
				"offset": offset,
			}
		)
		return await self._service.list_community_posts(
			request.community_id,
			request.viewer_id,
			limit=request.limit,
			offset=request.offset,
		)


__all__ = ["ContentFacade"]
