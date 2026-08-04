from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import CommunitiesBase


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class CommunityVisibility(str, Enum):
	PUBLIC = "public"
	PRIVATE = "private"


class Community(CommunitiesBase):
	__tablename__ = "communities"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	visibility: Mapped[CommunityVisibility] = mapped_column(
		SqlEnum(
			CommunityVisibility,
			name="community_visibility",
			native_enum=False,
			values_callable=lambda enum_type: [item.value for item in enum_type],
		),
		nullable=False,
		default=CommunityVisibility.PUBLIC,
	)
	owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

	members: Mapped[list[CommunityMember]] = relationship(
		back_populates="community",
		cascade="all, delete-orphan",
	)


class CommunityRole(CommunitiesBase):
	__tablename__ = "community_roles"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

	role_permissions: Mapped[list[CommunityRolePermission]] = relationship(
		back_populates="role",
		cascade="all, delete-orphan",
	)
	members: Mapped[list[CommunityMember]] = relationship(back_populates="role")


class CommunityPermission(CommunitiesBase):
	__tablename__ = "community_permissions"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)

	role_permissions: Mapped[list[CommunityRolePermission]] = relationship(
		back_populates="permission",
		cascade="all, delete-orphan",
	)


class CommunityRolePermission(CommunitiesBase):
	__tablename__ = "community_role_permissions"

	role_id: Mapped[UUID] = mapped_column(
		ForeignKey("community_roles.id", ondelete="CASCADE"),
		primary_key=True,
	)
	permission_id: Mapped[UUID] = mapped_column(
		ForeignKey("community_permissions.id", ondelete="CASCADE"),
		primary_key=True,
	)

	role: Mapped[CommunityRole] = relationship(back_populates="role_permissions")
	permission: Mapped[CommunityPermission] = relationship(back_populates="role_permissions")


class CommunityMember(CommunitiesBase):
	__tablename__ = "community_members"
	__table_args__ = (
		UniqueConstraint("user_id", "community_id", name="uq_community_members_user_community"),
	)

	id: Mapped[UUID] = mapped_column(primary_key=True)
	user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
	community_id: Mapped[UUID] = mapped_column(
		ForeignKey("communities.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	role_id: Mapped[UUID] = mapped_column(
		ForeignKey("community_roles.id", ondelete="RESTRICT"),
		nullable=False,
		index=True,
	)
	joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

	community: Mapped[Community] = relationship(back_populates="members")
	role: Mapped[CommunityRole] = relationship(back_populates="members")


__all__ = [
	"Community",
	"CommunityMember",
	"CommunityPermission",
	"CommunityRole",
	"CommunityRolePermission",
	"CommunityVisibility",
]
