from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SocialGraphUserLookupRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	user_id: UUID
	limit: Annotated[int, Field(ge=1, le=100)] = 50
	after: Annotated[str | None, Field(min_length=1, max_length=2048)] = None


__all__ = ["SocialGraphUserLookupRequest"]
