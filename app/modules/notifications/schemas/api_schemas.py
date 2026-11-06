from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CursorPageRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	limit: Annotated[int, Field(ge=1, le=100)] = 50
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


class CursorPageInfo(BaseModel):
	next_cursor: str | None
	has_more: bool


class NotificationResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	recipient_id: UUID
	type: str
	payload: dict[str, Any]
	is_read: bool
	created_at: datetime


class NotificationListResponse(BaseModel):
	notifications: list[NotificationResponse]
	page_info: CursorPageInfo


class NotificationReadAllResponse(BaseModel):
	detail: str


class NotificationWebSocketAuthPayload(BaseModel):
	token: str


__all__ = [
	"CursorPageRequest",
	"CursorPageInfo",
	"NotificationListResponse",
	"NotificationReadAllResponse",
	"NotificationResponse",
	"NotificationWebSocketAuthPayload",
]
