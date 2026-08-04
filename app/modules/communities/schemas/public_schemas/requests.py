from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CommunityLookupRequest(BaseModel):
	community_id: UUID


class CommunityMembershipLookupRequest(BaseModel):
	community_id: UUID
	user_id: UUID


class CommunityAccessLookupRequest(BaseModel):
	community_id: UUID
	viewer_id: UUID | None = None


class AccessibleCommunitiesLookupRequest(BaseModel):
	viewer_id: UUID | None = None


__all__ = [
	"AccessibleCommunitiesLookupRequest",
	"CommunityAccessLookupRequest",
	"CommunityLookupRequest",
	"CommunityMembershipLookupRequest",
]
