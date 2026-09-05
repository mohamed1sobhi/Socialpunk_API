from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.admins.schemas.api_schemas import (
	RefreshTokenRequest,
	RoleAssignmentRequest,
	RoleAssignmentResponse,
	RoleCreateRequest,
	RoleListResponse,
	RoleResponse,
	RoleUpdateRequest,
	SystemUserCreateRequest,
	SystemUserPermissionsResponse,
	SystemUserResponse,
	SystemUserUpdateRequest,
	TokenPairResponse,
)
from app.shared.auth.dependencies import require_system_permission
from app.shared.dependencies.admins_deps import get_admin_service


MANAGE_SYSTEM_USERS_PERMISSION = "admins.system_users.manage"
VIEW_SYSTEM_USERS_PERMISSION = "admins.system_users.read"
MANAGE_ROLES_PERMISSION = "admins.roles.manage"
VIEW_SYSTEM_PERMISSIONS_PERMISSION = "admins.system_permissions.read"


router = APIRouter(prefix="/admins", tags=["admins"])


@router.post("/login", response_model=TokenPairResponse)
async def login_system_user(
	form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
	service: Annotated[Any, Depends(get_admin_service)],
) -> TokenPairResponse:
	tokens = await service.login(email=form_data.username, password=form_data.password)
	return TokenPairResponse.model_validate(tokens)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_system_user_tokens(
	payload: RefreshTokenRequest,
	service: Annotated[Any, Depends(get_admin_service)],
) -> TokenPairResponse:
	tokens = await service.refresh_tokens(refresh_token=payload.refresh_token)
	return TokenPairResponse.model_validate(tokens)


@router.post(
	"/system-users",
	response_model=SystemUserResponse,
	status_code=status.HTTP_201_CREATED,
)
async def create_system_user(
	payload: SystemUserCreateRequest,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_SYSTEM_USERS_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> SystemUserResponse:
	del current_user
	system_user = await service.create_system_user(
		payload.model_dump(exclude={"role_names"}),
		payload.role_names,
	)
	return SystemUserResponse.model_validate(system_user)


@router.get("/system-users/{user_id}", response_model=SystemUserResponse)
async def get_system_user(
	user_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(VIEW_SYSTEM_USERS_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> SystemUserResponse:
	del current_user
	system_user = await service.get_system_user(user_id)
	return SystemUserResponse.model_validate(system_user)


@router.patch("/system-users/{user_id}", response_model=SystemUserResponse)
async def update_system_user(
	user_id: UUID,
	payload: SystemUserUpdateRequest,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_SYSTEM_USERS_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> SystemUserResponse:
	del current_user
	system_user = await service.update_system_user(user_id, payload.model_dump(exclude_unset=True))
	return SystemUserResponse.model_validate(system_user)


@router.delete("/system-users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def deactivate_system_user(
	user_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_SYSTEM_USERS_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> Response:
	del current_user
	await service.deactivate_system_user(user_id)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_ROLES_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> RoleListResponse:
	del current_user
	roles = await service.list_roles()
	return RoleListResponse.model_validate(roles)


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
	payload: RoleCreateRequest,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_ROLES_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> RoleResponse:
	del current_user
	role = await service.create_role(
		name=payload.name,
		description=payload.description,
		permission_flags=payload.model_dump(exclude={"name", "description"}),
	)
	return RoleResponse.model_validate(role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
	role_id: UUID,
	payload: RoleUpdateRequest,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_ROLES_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> RoleResponse:
	del current_user
	role = await service.update_role(role_id, payload.model_dump(exclude_unset=True))
	return RoleResponse.model_validate(role)


@router.post(
	"/system-users/{user_id}/roles",
	response_model=RoleAssignmentResponse,
	status_code=status.HTTP_201_CREATED,
)
async def assign_role_to_system_user(
	user_id: UUID,
	payload: RoleAssignmentRequest,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_ROLES_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> RoleAssignmentResponse:
	del current_user
	assignment = await service.assign_role(user_id, role_name=payload.role_name)
	return RoleAssignmentResponse.model_validate(assignment)


@router.delete(
	"/system-users/{user_id}/roles/{role_id}",
	status_code=status.HTTP_204_NO_CONTENT,
	response_class=Response,
)
async def revoke_role_from_system_user(
	user_id: UUID,
	role_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_system_permission(MANAGE_ROLES_PERMISSION))],
	service: Annotated[Any, Depends(get_admin_service)],
) -> Response:
	del current_user
	await service.revoke_role(user_id, role_id)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/system-users/{user_id}/permissions", response_model=SystemUserPermissionsResponse)
async def get_system_user_permissions(
	user_id: UUID,
	current_user: Annotated[
		dict[str, Any],
		Depends(require_system_permission(VIEW_SYSTEM_PERMISSIONS_PERMISSION)),
	],
	service: Annotated[Any, Depends(get_admin_service)],
) -> SystemUserPermissionsResponse:
	del current_user
	permissions = await service.get_permissions_for_user(user_id)
	return SystemUserPermissionsResponse.model_validate(permissions)
