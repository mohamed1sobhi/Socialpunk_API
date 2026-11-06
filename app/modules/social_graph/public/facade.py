from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.social_graph.schemas.public_schemas.requests import SocialGraphUserLookupRequest


class SocialGraphServiceProtocol(Protocol):
	async def get_friends(self, user_id: UUID | str, *, limit: int = 50, after: str | None = None) -> dict[str, Any]: ...
	async def get_pending_requests(self, user_id: UUID | str, *, limit: int = 50, after: str | None = None) -> dict[str, Any]: ...


class SocialGraphFacade:
	def __init__(self, service: SocialGraphServiceProtocol) -> None:
		self._service = service

	async def get_friends(self, user_id: UUID | str, *, limit: int = 50, after: str | None = None) -> dict[str, Any]:
		request = SocialGraphUserLookupRequest.model_validate({"user_id": user_id, "limit": limit, "after": after})
		return await self._service.get_friends(request.user_id, limit=request.limit, after=request.after)

	async def get_pending_requests(self, user_id: UUID | str, *, limit: int = 50, after: str | None = None) -> dict[str, Any]:
		request = SocialGraphUserLookupRequest.model_validate({"user_id": user_id, "limit": limit, "after": after})
		return await self._service.get_pending_requests(request.user_id, limit=request.limit, after=request.after)


__all__ = ["SocialGraphFacade"]
