from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class NotificationUserContactResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	username: str
	email: EmailStr
	is_active: bool
	created_at: datetime
	phone_number: str | None = None


class NotificationCommunityOwnerResponse(BaseModel):
	community_id: UUID
	owner_id: UUID


class MemberIdsPageInfo(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)
	next_cursor: Annotated[str | None, Field(min_length=1, max_length=2048)]
	has_more: bool

	@model_validator(mode="after")
	def validate_continuation(self) -> Self:
		if self.has_more != (self.next_cursor is not None):
			raise ValueError("has_more must match next_cursor availability")
		return self


class NotificationCommunityMembersResponse(BaseModel):
	community_id: UUID
	member_ids: Annotated[list[UUID], Field(max_length=1000)]
	page_info: MemberIdsPageInfo

	@model_validator(mode="after")
	def validate_nonempty_continuation(self) -> Self:
		if self.page_info.has_more and not self.member_ids:
			raise ValueError("A continuing member batch must not be empty")
		return self


class NotificationResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	recipient_id: UUID
	type: str
	payload: dict[str, Any]
	is_read: bool
	created_at: datetime


__all__ = [
	"NotificationCommunityMembersResponse",
	"NotificationCommunityOwnerResponse",
	"NotificationResponse",
	"NotificationUserContactResponse",
]
