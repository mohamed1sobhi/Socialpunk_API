from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CursorPageRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	limit: Annotated[int, Field(ge=1, le=100)] = 50
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


class CursorPageInfo(BaseModel):
	next_cursor: str | None
	has_more: bool


class CreateCommunityRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)

	name: Annotated[str, Field(min_length=3, max_length=150)]
	description: Annotated[str | None, Field(max_length=1000)] = None
	visibility: Literal["public", "private"]


class AssignCommunityRoleRequest(BaseModel):
	user_id: UUID


class CommunityResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	name: str
	description: str | None
	visibility: Literal["public", "private"]
	owner_id: UUID
	created_at: datetime


class CommunityListResponse(BaseModel):
	communities: list[CommunityResponse]
	page_info: CursorPageInfo


class CommunityMemberResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	user_id: UUID
	community_id: UUID
	role_id: UUID
	joined_at: datetime


class CommunityMembersResponse(BaseModel):
	community_id: UUID
	members: list[CommunityMemberResponse]
	page_info: CursorPageInfo


class CommunityRoleResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	name: str
	permission_names: list[str]


class CommunityRolesResponse(BaseModel):
	roles: list[CommunityRoleResponse]


class CommunityPermissionResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	name: str


class CommunityPermissionsResponse(BaseModel):
	permissions: list[CommunityPermissionResponse]


__all__ = [
	"CursorPageRequest",
	"CursorPageInfo",
	"AssignCommunityRoleRequest",
	"CommunityListResponse",
	"CommunityMemberResponse",
	"CommunityMembersResponse",
	"CommunityPermissionResponse",
	"CommunityPermissionsResponse",
	"CommunityResponse",
	"CommunityRoleResponse",
	"CommunityRolesResponse",
	"CreateCommunityRequest",
]
