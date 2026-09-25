from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.users.schemas.api_schemas import (
	RefreshTokenRequest,
	RegisterUserRequest,
	TokenPairResponse,
	UserAccountUpdateRequest,
	UserProfileResponse,
	UserProfileUpdateRequest,
	UserResponse,
)
from app.shared.auth.dependencies import require_permission
from app.shared.dependencies.users_deps import get_user_service


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
	payload: RegisterUserRequest,
	service: Annotated[Any, Depends(get_user_service)],
) -> UserResponse:
	user = await service.register(
		username=payload.username,
		email=str(payload.email),
		password=payload.password,
	)
	return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenPairResponse)
async def login_user(
	form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
	service: Annotated[Any, Depends(get_user_service)],
) -> TokenPairResponse:
	tokens = await service.login(email=form_data.username, password=form_data.password)
	return TokenPairResponse.model_validate(tokens)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_user_tokens(
	payload: RefreshTokenRequest,
	service: Annotated[Any, Depends(get_user_service)],
) -> TokenPairResponse:
	tokens = await service.refresh_tokens(refresh_token=payload.refresh_token)
	return TokenPairResponse.model_validate(tokens)


@router.patch("/me", response_model=UserResponse)
async def update_my_account(
	payload: UserAccountUpdateRequest,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_user_service)],
) -> UserResponse:
	updated_user = await service.update_user(current_user["sub"], payload.model_dump(exclude_unset=True))
	return UserResponse.model_validate(updated_user)


@router.patch("/me/profile", response_model=UserProfileResponse)
async def update_my_profile(
	payload: UserProfileUpdateRequest,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_user_service)],
) -> UserProfileResponse:
	updated_profile = await service.update_profile(current_user["sub"], payload.model_dump(exclude_unset=True))
	return UserProfileResponse.model_validate(updated_profile)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_my_account(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_user_service)],
) -> Response:
	await service.delete_user(current_user["sub"])
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
	user_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_user_service)],
) -> UserResponse:
	del current_user
	user = await service.get_user(user_id)
	return UserResponse.model_validate(user)


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
	user_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_user_service)],
) -> UserProfileResponse:
	del current_user
	profile = await service.get_profile(user_id)
	return UserProfileResponse.model_validate(profile)
