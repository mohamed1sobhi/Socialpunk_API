from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.communities.schemas.public_schemas.requests import (
	AccessibleCommunitiesLookupRequest,
	CommunityAccessLookupRequest,
	CommunityLookupRequest,
	CommunityMembershipLookupRequest,
)


class CommunityServiceProtocol(Protocol):
	async def get_access(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None,
	) -> dict[str, Any]: ...
	async def list_accessible_community_ids(self, viewer_id: UUID | str | None) -> dict[str, Any]: ...
	async def get_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]: ...
	async def is_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]: ...
	async def get_owner(self, community_id: UUID | str) -> dict[str, Any]: ...
	async def list_member_ids(self, community_id: UUID | str) -> dict[str, Any]: ...
	async def list_roles(self) -> dict[str, Any]: ...
	async def list_permissions(self) -> dict[str, Any]: ...


class CommunityFacade:
	def __init__(self, service: CommunityServiceProtocol) -> None:
		self._service = service

	async def get_access(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		request = CommunityAccessLookupRequest.model_validate(
			{"community_id": community_id, "viewer_id": viewer_id}
		)
		return await self._service.get_access(request.community_id, request.viewer_id)

	async def list_accessible_community_ids(
		self,
		viewer_id: UUID | str | None = None,
	) -> dict[str, Any]:
		request = AccessibleCommunitiesLookupRequest.model_validate({"viewer_id": viewer_id})
		return await self._service.list_accessible_community_ids(request.viewer_id)

	async def get_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		request = CommunityMembershipLookupRequest.model_validate(
			{"user_id": user_id, "community_id": community_id}
		)
		return await self._service.get_member(request.user_id, request.community_id)

	async def is_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		request = CommunityMembershipLookupRequest.model_validate(
			{"user_id": user_id, "community_id": community_id}
		)
		return await self._service.is_member(request.user_id, request.community_id)

	async def get_owner(self, community_id: UUID | str) -> dict[str, Any]:
		request = CommunityLookupRequest.model_validate({"community_id": community_id})
		return await self._service.get_owner(request.community_id)

	async def list_member_ids(self, community_id: UUID | str) -> dict[str, Any]:
		request = CommunityLookupRequest.model_validate({"community_id": community_id})
		return await self._service.list_member_ids(request.community_id)

	async def list_roles(self) -> dict[str, Any]:
		return await self._service.list_roles()

	async def list_permissions(self) -> dict[str, Any]:
		return await self._service.list_permissions()


__all__ = ["CommunityFacade"]
