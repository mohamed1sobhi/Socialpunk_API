from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.modules.communities.schemas.api_schemas import (
	AssignCommunityRoleRequest,
	CommunityListResponse,
	CommunityMemberResponse,
	CommunityMembersResponse,
	CommunityPermissionsResponse,
	CommunityResponse,
	CommunityRoleResponse,
	CommunityRolesResponse,
	CreateCommunityRequest,
)
from app.shared.auth.dependencies import require_permission
from app.shared.dependencies.communities_deps import get_community_service


router = APIRouter(prefix="/communities", tags=["communities"])


@router.post("", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
async def create_community(
	payload: CreateCommunityRequest,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityResponse:
	community = await service.create_community(current_user["sub"], payload.model_dump())
	return CommunityResponse.model_validate(community)


@router.get("", response_model=CommunityListResponse)
async def list_public_communities(
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityListResponse:
	communities = await service.list_public_communities()
	return CommunityListResponse.model_validate(communities)


@router.get("/roles", response_model=CommunityRolesResponse)
async def list_community_roles(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityRolesResponse:
	del current_user
	roles = await service.list_roles()
	return CommunityRolesResponse.model_validate(roles)


@router.get("/permissions", response_model=CommunityPermissionsResponse)
async def list_community_permissions(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityPermissionsResponse:
	del current_user
	permissions = await service.list_permissions()
	return CommunityPermissionsResponse.model_validate(permissions)


@router.get("/{community_id}", response_model=CommunityResponse)
async def get_community(
	community_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityResponse:
	community = await service.get_community(community_id, current_user["sub"])
	return CommunityResponse.model_validate(community)


@router.post("/{community_id}/join", response_model=CommunityMemberResponse)
async def join_community(
	community_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityMemberResponse:
	member = await service.join_community(current_user["sub"], community_id)
	return CommunityMemberResponse.model_validate(member)


@router.post("/{community_id}/leave", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def leave_community(
	community_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> Response:
	await service.leave_community(current_user["sub"], community_id)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{community_id}/members", response_model=CommunityMembersResponse)
async def list_community_members(
	community_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityMembersResponse:
	members = await service.list_members(current_user["sub"], community_id)
	return CommunityMembersResponse.model_validate(members)


@router.post("/{community_id}/roles/{role_id}/assign", response_model=CommunityMemberResponse)
async def assign_community_role(
	community_id: UUID,
	role_id: UUID,
	payload: AssignCommunityRoleRequest,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_community_service)],
) -> CommunityMemberResponse:
	await service.get_member(current_user["sub"], community_id)
	await service.get_member(payload.user_id, community_id)
	await service.require_community_permission(
		current_user["sub"],
		community_id,
		"communities.members.manage",
	)
	member = await service.assign_role_to_member(community_id, payload.user_id, role_id)
	return CommunityMemberResponse.model_validate(member)
