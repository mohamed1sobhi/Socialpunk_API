from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admins.models.models import AdminUser, Role, UserRole


class AdminRepository:
	def __init__(self, session: AsyncSession) -> None:
		self._session = session

	async def get_user_by_id(self, user_id: UUID) -> AdminUser | None:
		statement = select(AdminUser).where(AdminUser.id == user_id)
		return await self._session.scalar(statement)

	async def get_user_by_email(self, email: str) -> AdminUser | None:
		statement = select(AdminUser).where(AdminUser.email == email)
		return await self._session.scalar(statement)

	async def get_user_by_username(self, username: str) -> AdminUser | None:
		statement = select(AdminUser).where(AdminUser.username == username)
		return await self._session.scalar(statement)

	async def create_user(self, data: dict[str, Any]) -> AdminUser:
		user = AdminUser(**data)
		self._session.add(user)
		await self._session.flush()
		return user

	async def update_user(self, user_id: UUID, data: dict[str, Any]) -> AdminUser | None:
		user = await self.get_user_by_id(user_id)
		if user is None:
			return None

		for field_name, value in data.items():
			setattr(user, field_name, value)

		await self._session.flush()
		return user

	async def deactivate_user(self, user_id: UUID) -> AdminUser | None:
		user = await self.get_user_by_id(user_id)
		if user is None:
			return None

		user.is_active = False
		await self._session.flush()
		return user

	async def get_role_by_id(self, role_id: UUID) -> Role | None:
		statement = select(Role).where(Role.id == role_id)
		return await self._session.scalar(statement)

	async def get_role_by_name(self, name: str) -> Role | None:
		statement = select(Role).where(Role.name == name)
		return await self._session.scalar(statement)

	async def create_role(self, data: dict[str, Any]) -> Role:
		role = Role(**data)
		self._session.add(role)
		await self._session.flush()
		return role

	async def list_roles(self) -> list[Role]:
		statement = select(Role).order_by(Role.name.asc())
		return list((await self._session.scalars(statement)).all())

	async def update_role(self, role_id: UUID, data: dict[str, Any]) -> Role | None:
		role = await self.get_role_by_id(role_id)
		if role is None:
			return None

		for field_name, value in data.items():
			setattr(role, field_name, value)

		await self._session.flush()
		return role

	async def get_user_role(self, user_id: UUID, role_id: UUID) -> UserRole | None:
		statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
		return await self._session.scalar(statement)

	async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> UserRole:
		user_role = UserRole(user_id=user_id, role_id=role_id)
		self._session.add(user_role)
		await self._session.flush()
		return user_role

	async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> bool:
		user_role = await self.get_user_role(user_id, role_id)
		if user_role is None:
			return False

		await self._session.delete(user_role)
		await self._session.flush()
		return True

	async def get_user_roles(self, user_id: UUID) -> list[Role]:
		statement = (
			select(Role)
			.join(UserRole, UserRole.role_id == Role.id)
			.where(UserRole.user_id == user_id)
			.order_by(Role.name.asc())
		)
		result = await self._session.scalars(statement)
		return list(result)

	async def get_user_permissions(self, user_id: UUID) -> list[str]:
		roles = await self.get_user_roles(user_id)
		return sorted({permission for role in roles for permission in role.permission_names})


__all__ = ["AdminRepository"]
