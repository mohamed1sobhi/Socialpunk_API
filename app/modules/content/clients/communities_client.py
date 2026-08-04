from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.content.schemas.public_schemas.responses import (
	ContentAccessibleCommunityIdsResponse,
	ContentCommunityAccessResponse,
	ContentCommunityMembershipResponse,
)


class CommunityFacadeProtocol(Protocol):
	async def get_access(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]: ...
	async def list_accessible_community_ids(
		self,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]: ...
	async def is_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]: ...


class CommunitiesClient:
	def __init__(self, communities_facade: CommunityFacadeProtocol) -> None:
		self._communities_facade = communities_facade

	async def get_access(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		payload = await self._communities_facade.get_access(community_id, viewer_id)
		response = ContentCommunityAccessResponse.model_validate(payload)
		return response.model_dump()

	async def list_accessible_community_ids(
		self,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		payload = await self._communities_facade.list_accessible_community_ids(viewer_id)
		response = ContentAccessibleCommunityIdsResponse.model_validate(payload)
		return response.model_dump()

	async def is_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		payload = await self._communities_facade.is_member(user_id, community_id)
		response = ContentCommunityMembershipResponse.model_validate(payload)
		return response.model_dump()


__all__ = ["CommunitiesClient"]
