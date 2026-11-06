from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CursorPageRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	limit: Annotated[int, Field(ge=1, le=100)] = 50
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


class CursorPageInfo(BaseModel):
	next_cursor: str | None
	has_more: bool


class CreatePostRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

	community_id: UUID
	title: Annotated[str | None, Field(max_length=200)] = None
	body: Annotated[str, Field(min_length=1)]


class PostResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	author_id: UUID
	community_id: UUID
	title: str | None
	body: str
	created_at: datetime
	updated_at: datetime
	is_deleted: bool


class PostListResponse(BaseModel):
	posts: list[PostResponse]
	page_info: CursorPageInfo


class UserPostsResponse(BaseModel):
	author_id: UUID
	posts: list[PostResponse]
	page_info: CursorPageInfo


class CommunityPostsResponse(BaseModel):
	community_id: UUID
	posts: list[PostResponse]
	page_info: CursorPageInfo


__all__ = [
	"CursorPageRequest",
	"CursorPageInfo",
	"CommunityPostsResponse",
	"CreatePostRequest",
	"PostListResponse",
	"PostResponse",
	"UserPostsResponse",
]
