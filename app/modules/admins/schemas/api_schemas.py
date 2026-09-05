from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RefreshTokenRequest(BaseModel):
	refresh_token: Annotated[str, Field(min_length=1)]


class SystemUserCreateRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)

	username: Annotated[str, Field(min_length=3, max_length=50)]
	email: EmailStr
	password: Annotated[str, Field(min_length=8, max_length=128)]
	role_names: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list)


class SystemUserUpdateRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)

	username: Annotated[str | None, Field(min_length=3, max_length=50)] = None
	email: EmailStr | None = None
	password: Annotated[str | None, Field(min_length=8, max_length=128)] = None

	@model_validator(mode="after")
	def validate_non_empty_update(self) -> Self:
		if self.username is None and self.email is None and self.password is None:
			raise ValueError("At least one system-user field must be provided")
		return self


class RoleCreateRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)

	name: Annotated[str, Field(min_length=1, max_length=100)]
	description: Annotated[str | None, Field(max_length=500)] = None
	can_manage_system_users: bool = False
	can_read_system_users: bool = False
	can_manage_roles: bool = False
	can_read_system_permissions: bool = False


class RoleUpdateRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)

	name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
	description: Annotated[str | None, Field(max_length=500)] = None
	can_manage_system_users: bool | None = None
	can_read_system_users: bool | None = None
	can_manage_roles: bool | None = None
	can_read_system_permissions: bool | None = None

	@model_validator(mode="after")
	def validate_non_empty_update(self) -> Self:
		if not self.model_fields_set:
			raise ValueError("At least one role field must be provided")
		return self


class RoleAssignmentRequest(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)

	role_name: Annotated[str, Field(min_length=1, max_length=100)]


class TokenPairResponse(BaseModel):
	access_token: str
	refresh_token: str
	token_type: Literal["bearer"]


class SystemUserResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	username: str
	email: EmailStr
	is_active: bool
	created_at: datetime
	role_names: list[str]


class RoleResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	name: str
	description: str | None
	can_manage_system_users: bool
	can_read_system_users: bool
	can_manage_roles: bool
	can_read_system_permissions: bool


class RoleListResponse(BaseModel):
	roles: list[RoleResponse]


class RoleAssignmentResponse(BaseModel):
	user_id: UUID
	role_id: UUID
	role_name: str
	assigned_at: datetime


class SystemUserPermissionsResponse(BaseModel):
	user_id: UUID
	permissions: list[str]


__all__ = [
	"RefreshTokenRequest",
	"RoleAssignmentRequest",
	"RoleAssignmentResponse",
	"RoleCreateRequest",
	"RoleListResponse",
	"RoleResponse",
	"RoleUpdateRequest",
	"SystemUserCreateRequest",
	"SystemUserPermissionsResponse",
	"SystemUserResponse",
	"SystemUserUpdateRequest",
	"TokenPairResponse",
]
