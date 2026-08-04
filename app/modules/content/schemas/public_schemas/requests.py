from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ContentPostLookupRequest(BaseModel):
	post_id: UUID
	viewer_id: UUID | None = None


class ContentUserPostsLookupRequest(BaseModel):
	author_id: UUID
	viewer_id: UUID | None = None


class ContentCommunityPostsLookupRequest(BaseModel):
	community_id: UUID
	viewer_id: UUID | None = None
	limit: int = 50
	offset: int = 0


__all__ = [
	"ContentCommunityPostsLookupRequest",
	"ContentPostLookupRequest",
	"ContentUserPostsLookupRequest",
]
