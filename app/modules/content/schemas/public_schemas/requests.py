from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentPostLookupRequest(BaseModel):
	post_id: UUID
	viewer_id: UUID | None = None


class ContentUserPostsLookupRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	author_id: UUID
	viewer_id: UUID | None = None
	limit: Annotated[int, Field(ge=1, le=100)] = 50
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


class ContentCommunityPostsLookupRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	community_id: UUID
	viewer_id: UUID | None = None
	limit: Annotated[int, Field(ge=1, le=100)] = 50
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


__all__ = [
	"ContentCommunityPostsLookupRequest",
	"ContentPostLookupRequest",
	"ContentUserPostsLookupRequest",
]
