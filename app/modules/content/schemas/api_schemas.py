from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class UserPostsResponse(BaseModel):
	author_id: UUID
	posts: list[PostResponse]


class CommunityPostsResponse(BaseModel):
	community_id: UUID
	posts: list[PostResponse]


__all__ = [
	"CommunityPostsResponse",
	"CreatePostRequest",
	"PostListResponse",
	"PostResponse",
	"UserPostsResponse",
]
