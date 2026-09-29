from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admins.models.models import AdminUser, Role, UserRole


class AdminRepository:
	def __init__(self, session: AsyncSession) -> None:
		self._session = session

	@staticmethod
	def _user_payload(user: AdminUser) -> dict[str, Any]:
		return {field: getattr(user, field) for field in (
			"id", "username", "email", "hashed_password", "is_active", "created_at",
		)}

	@staticmethod
	def _role_payload(role: Role) -> dict[str, Any]:
		return {field: getattr(role, field) for field in (
			"id", "name", "description", "can_manage_system_users", "can_read_system_users",
			"can_manage_roles", "can_read_system_permissions", "can_delete_posts",
		)}

	async def _get_user(self, user_id: UUID) -> AdminUser | None:
		statement = select(AdminUser).where(AdminUser.id == user_id)
		return await self._session.scalar(statement)

	async def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
		user = await self._get_user(user_id)
		return self._user_payload(user) if user is not None else None

	async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
		statement = select(AdminUser).where(AdminUser.email == email)
		user = await self._session.scalar(statement)
		return self._user_payload(user) if user is not None else None

	async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
		statement = select(AdminUser).where(AdminUser.username == username)
		user = await self._session.scalar(statement)
		return self._user_payload(user) if user is not None else None

	async def create_user(self, data: dict[str, Any]) -> dict[str, Any]:
		user = AdminUser(**data)
		self._session.add(user)
		await self._session.flush()
		return self._user_payload(user)

	async def update_user(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
		user = await self._get_user(user_id)
		if user is None:
			return None

		for field_name, value in data.items():
			setattr(user, field_name, value)

		await self._session.flush()
		return self._user_payload(user)

	async def deactivate_user(self, user_id: UUID) -> dict[str, Any] | None:
		user = await self._get_user(user_id)
		if user is None:
			return None

		user.is_active = False
		await self._session.flush()
		return self._user_payload(user)

	async def _get_role(self, role_id: UUID) -> Role | None:
		statement = select(Role).where(Role.id == role_id)
		return await self._session.scalar(statement)

	async def get_role_by_id(self, role_id: UUID) -> dict[str, Any] | None:
		role = await self._get_role(role_id)
		return self._role_payload(role) if role is not None else None

	async def get_role_by_name(self, name: str) -> dict[str, Any] | None:
		statement = select(Role).where(Role.name == name)
		role = await self._session.scalar(statement)
		return self._role_payload(role) if role is not None else None

	async def create_role(self, data: dict[str, Any]) -> dict[str, Any]:
		role = Role(**data)
		self._session.add(role)
		await self._session.flush()
		return self._role_payload(role)

	async def list_roles(self) -> list[dict[str, Any]]:
		statement = select(Role).order_by(Role.name.asc())
		return [self._role_payload(role) for role in (await self._session.scalars(statement)).all()]

	async def update_role(self, role_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
		role = await self._get_role(role_id)
		if role is None:
			return None

		for field_name, value in data.items():
			setattr(role, field_name, value)

		await self._session.flush()
		return self._role_payload(role)

	async def _get_user_role(self, user_id: UUID, role_id: UUID) -> UserRole | None:
		statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
		return await self._session.scalar(statement)

	async def get_user_role(self, user_id: UUID, role_id: UUID) -> dict[str, Any] | None:
		assignment = await self._get_user_role(user_id, role_id)
		return self._assignment_payload(assignment) if assignment is not None else None

	@staticmethod
	def _assignment_payload(assignment: UserRole) -> dict[str, Any]:
		return {field: getattr(assignment, field) for field in ("user_id", "role_id", "assigned_at")}

	async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> dict[str, Any]:
		user_role = UserRole(user_id=user_id, role_id=role_id)
		self._session.add(user_role)
		await self._session.flush()
		return self._assignment_payload(user_role)

	async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> bool:
		user_role = await self._get_user_role(user_id, role_id)
		if user_role is None:
			return False

		await self._session.delete(user_role)
		await self._session.flush()
		return True

	async def get_user_roles(self, user_id: UUID) -> list[dict[str, Any]]:
		statement = (
			select(Role)
			.join(UserRole, UserRole.role_id == Role.id)
			.where(UserRole.user_id == user_id)
			.order_by(Role.name.asc())
		)
		result = await self._session.scalars(statement)
		return [self._role_payload(role) for role in result]

	async def get_user_permissions(self, user_id: UUID) -> list[str]:
		statement = select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
		roles = (await self._session.scalars(statement)).all()
		return sorted({permission for role in roles for permission in role.permission_names})


__all__ = ["AdminRepository"]
