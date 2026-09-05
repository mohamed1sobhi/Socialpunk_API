from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import AdminsBase


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class AdminUser(AdminsBase):
	__tablename__ = "users"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
	email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
	hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

	user_roles: Mapped[list[UserRole]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(AdminsBase):
	__tablename__ = "roles"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	can_manage_system_users: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	can_read_system_users: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	can_manage_roles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	can_read_system_permissions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

	user_roles: Mapped[list[UserRole]] = relationship(back_populates="role", cascade="all, delete-orphan")

	@property
	def permission_names(self) -> list[str]:
		permissions: list[str] = []
		if self.can_manage_system_users:
			permissions.append("admins.system_users.manage")
		if self.can_read_system_users:
			permissions.append("admins.system_users.read")
		if self.can_manage_roles:
			permissions.append("admins.roles.manage")
		if self.can_read_system_permissions:
			permissions.append("admins.system_permissions.read")
		return permissions


class UserRole(AdminsBase):
	__tablename__ = "user_roles"

	user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
	role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
	assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

	user: Mapped[AdminUser] = relationship(back_populates="user_roles")
	role: Mapped[Role] = relationship(back_populates="user_roles")


__all__ = ["AdminUser", "Role", "UserRole"]
