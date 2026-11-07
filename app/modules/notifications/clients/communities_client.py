from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.notifications.schemas.public_schemas.responses import (
	NotificationCommunityMembersResponse,
	NotificationCommunityOwnerResponse,
)


class CommunityFacadeProtocol(Protocol):
	async def get_owner(self, community_id: UUID | str) -> dict[str, Any]: ...
	async def list_member_ids(self, community_id: UUID | str, *, limit: int = 500, after: str | None = None) -> dict[str, Any]: ...


class CommunitiesClient:
	def __init__(self, communities_facade: CommunityFacadeProtocol) -> None:
		self._communities_facade = communities_facade

	async def get_owner(self, community_id: UUID | str) -> dict[str, Any]:
		payload = await self._communities_facade.get_owner(community_id)
		response = NotificationCommunityOwnerResponse.model_validate(payload)
		return response.model_dump()

	async def list_member_ids(self, community_id: UUID | str, *, limit: int = 500, after: str | None = None) -> dict[str, Any]:
		payload = await self._communities_facade.list_member_ids(community_id, limit=limit, after=after)
		response = NotificationCommunityMembersResponse.model_validate(payload)
		return response.model_dump()


__all__ = ["CommunitiesClient"]
