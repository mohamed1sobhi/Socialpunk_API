from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.modules.content.schemas.api_schemas import (
	CommunityPostsResponse,
	CreatePostRequest,
	PostListResponse,
	PostResponse,
	UserPostsResponse,
)
from app.shared.auth.dependencies import get_current_user, oauth2_scheme
from app.shared.dependencies.content_deps import get_content_service


CONTENT_POSTS_DELETE_PERMISSION = "content.posts.delete"

router = APIRouter(tags=["content"])


async def _get_optional_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any] | None:
	if token is None:
		return None
	return await get_current_user(token)


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
	payload: CreatePostRequest,
	current_user: Annotated[dict[str, Any], Depends(get_current_user)],
	service: Annotated[Any, Depends(get_content_service)],
) -> PostResponse:
	post = await service.create_post(current_user["sub"], payload.model_dump())
	return PostResponse.model_validate(post)


@router.get("/posts", response_model=PostListResponse)
async def list_feed(
	current_user: Annotated[dict[str, Any] | None, Depends(_get_optional_current_user)],
	service: Annotated[Any, Depends(get_content_service)],
	limit: Annotated[int, Query(ge=1, le=100)] = 50,
	offset: Annotated[int, Query(ge=0)] = 0,
) -> PostListResponse:
	viewer_id = current_user["sub"] if current_user is not None else None
	posts = await service.list_feed(viewer_id, limit=limit, offset=offset)
	return PostListResponse.model_validate(posts)


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
	post_id: UUID,
	current_user: Annotated[dict[str, Any] | None, Depends(_get_optional_current_user)],
	service: Annotated[Any, Depends(get_content_service)],
) -> PostResponse:
	viewer_id = current_user["sub"] if current_user is not None else None
	post = await service.get_post(post_id, viewer_id)
	return PostResponse.model_validate(post)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_post(
	post_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(get_current_user)],
	service: Annotated[Any, Depends(get_content_service)],
) -> Response:
	can_delete_any = CONTENT_POSTS_DELETE_PERMISSION in current_user.get("system_permissions", [])
	await service.delete_post(post_id, current_user["sub"], can_delete_any=can_delete_any)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/posts", response_model=UserPostsResponse)
async def list_user_posts(
	user_id: UUID,
	current_user: Annotated[dict[str, Any] | None, Depends(_get_optional_current_user)],
	service: Annotated[Any, Depends(get_content_service)],
) -> UserPostsResponse:
	viewer_id = current_user["sub"] if current_user is not None else None
	posts = await service.list_user_posts(user_id, viewer_id)
	return UserPostsResponse.model_validate(posts)


@router.get("/communities/{community_id}/posts", response_model=CommunityPostsResponse)
async def list_community_posts(
	community_id: UUID,
	current_user: Annotated[dict[str, Any] | None, Depends(_get_optional_current_user)],
	service: Annotated[Any, Depends(get_content_service)],
	limit: Annotated[int, Query(ge=1, le=100)] = 50,
	offset: Annotated[int, Query(ge=0)] = 0,
) -> CommunityPostsResponse:
	viewer_id = current_user["sub"] if current_user is not None else None
	posts = await service.list_community_posts(
		community_id,
		viewer_id,
		limit=limit,
		offset=offset,
	)
	return CommunityPostsResponse.model_validate(posts)


__all__ = ["router"]
