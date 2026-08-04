from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContentCommunityMembershipResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	community_id: UUID
	user_id: UUID
	is_member: bool


class ContentCommunityAccessResponse(BaseModel):
	community_id: UUID
	can_view: bool
	is_member: bool


class ContentAccessibleCommunityIdsResponse(BaseModel):
	community_ids: list[UUID]


__all__ = [
	"ContentAccessibleCommunityIdsResponse",
	"ContentCommunityAccessResponse",
	"ContentCommunityMembershipResponse",
]
