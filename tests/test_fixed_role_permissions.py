from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.modules.admins.models.models import Role
from app.modules.admins.schemas.api_schemas import RoleCreateRequest, RoleUpdateRequest
from app.modules.admins.services.service import AdminService
from app.modules.communities.models.models import CommunityRole
from app.modules.communities.services.service import CommunityService
from app.shared.database.base import AdminsBase, CommunitiesBase


def test_admin_role_exposes_enabled_fixed_permissions() -> None:
	role = Role(
		id=uuid4(),
		name="user_manager",
		can_manage_system_users=True,
		can_read_system_users=False,
		can_manage_roles=True,
		can_read_system_permissions=False,
	)

	assert role.permission_names == ["admins.system_users.manage", "admins.roles.manage"]


def test_community_role_exposes_enabled_fixed_permissions() -> None:
	role = CommunityRole(
		id=uuid4(),
		name="moderator",
		can_manage_members=True,
		can_read_roles=False,
	)

	assert role.permission_names == ["communities.members.manage"]


def test_permission_tables_are_removed_from_metadata() -> None:
	assert set(AdminsBase.metadata.tables) == {"admins.users", "admins.roles", "admins.user_roles"}
	assert set(CommunitiesBase.metadata.tables) == {
		"communities.communities",
		"communities.community_roles",
		"communities.community_members",
	}


def test_role_request_supports_fixed_permission_flags() -> None:
	create_request = RoleCreateRequest(name="moderator", can_manage_roles=True)
	assert create_request.can_manage_roles is True
	assert create_request.can_manage_system_users is False

	update_request = RoleUpdateRequest(can_read_system_users=True)
	assert update_request.model_dump(exclude_unset=True) == {"can_read_system_users": True}

	with pytest.raises(ValueError, match="At least one role field"):
		RoleUpdateRequest()


class FakeAdminRoleRepository:
	def __init__(self) -> None:
		self.roles: dict[str, SimpleNamespace] = {}

	async def get_role_by_name(self, name: str) -> SimpleNamespace | None:
		return self.roles.get(name)

	async def get_role_by_id(self, role_id: Any) -> SimpleNamespace | None:
		return next((role for role in self.roles.values() if role.id == role_id), None)

	async def list_roles(self) -> list[SimpleNamespace]:
		return list(self.roles.values())

	async def create_role(self, data: dict[str, Any]) -> SimpleNamespace:
		for field_name in (
			"can_manage_system_users",
			"can_read_system_users",
			"can_manage_roles",
			"can_read_system_permissions",
		):
			data.setdefault(field_name, False)
		role = SimpleNamespace(**data)
		self.roles[role.name] = role
		return role

	async def update_role(self, role_id: Any, data: dict[str, Any]) -> SimpleNamespace | None:
		role = await self.get_role_by_id(role_id)
		if role is None:
			return None
		for field_name, value in data.items():
			setattr(role, field_name, value)
		return role


@pytest.mark.asyncio
async def test_admin_service_creates_and_updates_fixed_role_flags() -> None:
	repo = FakeAdminRoleRepository()
	service = AdminService(cast(Any, repo))

	created = await service.create_role(
		name="user_manager",
		permission_flags={"can_manage_system_users": True},
	)
	role_id = created["id"]

	assert created["can_manage_system_users"] is True
	assert created["can_manage_roles"] is False

	updated = await service.update_role(role_id, {"can_manage_roles": True})
	assert updated["can_manage_system_users"] is True
	assert updated["can_manage_roles"] is True


@pytest.mark.asyncio
async def test_community_service_returns_fixed_permission_catalog() -> None:
	service = CommunityService(cast(Any, object()), cast(Any, object()))

	permissions = await service.list_permissions()

	assert [permission["name"] for permission in permissions["permissions"]] == [
		"communities.members.manage",
		"communities.roles.read",
	]
	assert all(permission["id"] for permission in permissions["permissions"])
