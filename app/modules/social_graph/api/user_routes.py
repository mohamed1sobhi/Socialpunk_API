from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.social_graph.schemas.api_schemas import (
	FriendListResponse,
	FriendRequestResponse,
	FriendshipResponse,
	PendingFriendRequestsResponse,
	SendFriendRequestRequest,
)
from app.shared.auth.dependencies import require_permission
from app.shared.dependencies.social_graph_deps import get_social_graph_service


router = APIRouter(prefix="/social", tags=["social_graph"])


@router.post(
	"/friends/request",
	response_model=FriendRequestResponse,
	status_code=status.HTTP_201_CREATED,
)
async def send_friend_request(
	payload: SendFriendRequestRequest,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_social_graph_service)],
) -> FriendRequestResponse:
	friend_request = await service.send_request(
		requester_id=current_user["sub"],
		receiver_id=payload.receiver_id,
	)
	return FriendRequestResponse.model_validate(friend_request)


@router.post("/friends/{request_id}/accept", response_model=FriendshipResponse)
async def accept_friend_request(
	request_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_social_graph_service)],
) -> FriendshipResponse:
	friendship = await service.respond_to_request(
		responder_id=current_user["sub"],
		request_id=request_id,
		accept=True,
	)
	return FriendshipResponse.model_validate(friendship)


@router.post("/friends/{request_id}/reject", response_model=FriendRequestResponse)
async def reject_friend_request(
	request_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_social_graph_service)],
) -> FriendRequestResponse:
	friend_request = await service.respond_to_request(
		responder_id=current_user["sub"],
		request_id=request_id,
		accept=False,
	)
	return FriendRequestResponse.model_validate(friend_request)


@router.get("/friends", response_model=FriendListResponse)
async def list_friends(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_social_graph_service)],
) -> FriendListResponse:
	friends = await service.get_friends(current_user["sub"])
	return FriendListResponse.model_validate(friends)


@router.get("/friends/requests/pending", response_model=PendingFriendRequestsResponse)
async def list_pending_friend_requests(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_social_graph_service)],
) -> PendingFriendRequestsResponse:
	pending_requests = await service.get_pending_requests(current_user["sub"])
	return PendingFriendRequestsResponse.model_validate(pending_requests)
