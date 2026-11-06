from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommunityLookupRequest(BaseModel):
	community_id: UUID


class CommunityMemberIdsRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	community_id: UUID
	limit: Annotated[int, Field(ge=1, le=1000)] = 500
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


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
	"CommunityMemberIdsRequest",
]
