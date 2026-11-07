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


class SendFriendRequestRequest(BaseModel):
	receiver_id: UUID


class FriendRequestResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	requester_id: UUID
	receiver_id: UUID
	status: Literal["pending", "rejected"]
	created_at: datetime
	updated_at: datetime


class FriendshipResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	user_low: UUID
	user_high: UUID
	created_at: datetime


class FriendListResponse(BaseModel):
	user_id: UUID
	friend_ids: list[UUID]
	page_info: CursorPageInfo


class PendingFriendRequestsResponse(BaseModel):
	user_id: UUID
	requests: list[FriendRequestResponse]
	page_info: CursorPageInfo


__all__ = [
	"CursorPageRequest",
	"CursorPageInfo",
	"FriendListResponse",
	"FriendRequestResponse",
	"FriendshipResponse",
	"PendingFriendRequestsResponse",
	"SendFriendRequestRequest",
]
