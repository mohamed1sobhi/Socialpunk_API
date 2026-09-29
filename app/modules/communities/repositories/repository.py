from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.communities.models.models import (
	Community,
	CommunityMember,
	CommunityRole,
	CommunityVisibility,
)


class CommunityRepository:
	def __init__(self, session: AsyncSession) -> None:
		self._session = session

	@staticmethod
	def _community_payload(community: Community) -> dict[str, Any]:
		return {
			**{field: getattr(community, field) for field in (
				"id", "name", "description", "owner_id", "created_at",
			)},
			"visibility": community.visibility.value,
		}

	@staticmethod
	def _member_payload(member: CommunityMember) -> dict[str, Any]:
		return {field: getattr(member, field) for field in (
			"id", "user_id", "community_id", "role_id", "joined_at",
		)}

	@staticmethod
	def _role_payload(role: CommunityRole) -> dict[str, Any]:
		return {"id": role.id, "name": role.name}

	async def _get_community(self, community_id: UUID) -> Community | None:
		statement = select(Community).where(Community.id == community_id)
		return await self._session.scalar(statement)

	async def get_by_id(self, community_id: UUID) -> dict[str, Any] | None:
		community = await self._get_community(community_id)
		return self._community_payload(community) if community is not None else None

	async def list_public(self) -> list[dict[str, Any]]:
		statement = (
			select(Community)
			.where(Community.visibility == CommunityVisibility.PUBLIC)
			.order_by(Community.created_at.desc())
		)
		return [self._community_payload(row) for row in (await self._session.scalars(statement)).all()]

	async def list_accessible_ids(self, viewer_id: UUID | None) -> list[UUID]:
		statement = select(Community.id)
		if viewer_id is None:
			statement = statement.where(Community.visibility == CommunityVisibility.PUBLIC)
		else:
			statement = statement.outerjoin(
				CommunityMember,
				(CommunityMember.community_id == Community.id) & (CommunityMember.user_id == viewer_id),
			).where(
				or_(
					Community.visibility == CommunityVisibility.PUBLIC,
					Community.owner_id == viewer_id,
					CommunityMember.id.is_not(None),
				)
			)

		statement = statement.order_by(Community.created_at.desc(), Community.id.desc())
		return list((await self._session.scalars(statement)).all())

	async def create_community(self, data: dict[str, Any]) -> dict[str, Any]:
		community_data = dict(data)
		community_data["visibility"] = CommunityVisibility(community_data["visibility"])
		community = Community(**community_data)
		self._session.add(community)
		await self._session.flush()
		return self._community_payload(community)

	async def update_community(self, community_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
		community = await self._get_community(community_id)
		if community is None:
			return None

		for field_name, value in data.items():
			if field_name == "visibility":
				value = CommunityVisibility(value)
			setattr(community, field_name, value)

		await self._session.flush()
		return self._community_payload(community)

	async def delete_community(self, community_id: UUID) -> bool:
		community = await self._get_community(community_id)
		if community is None:
			return False

		await self._session.delete(community)
		await self._session.flush()
		return True

	async def _get_role(self, role_id: UUID) -> CommunityRole | None:
		statement = select(CommunityRole).where(CommunityRole.id == role_id)
		return await self._session.scalar(statement)

	async def get_role_by_id(self, role_id: UUID) -> dict[str, Any] | None:
		role = await self._get_role(role_id)
		return self._role_payload(role) if role is not None else None

	async def get_role_by_name(self, name: str) -> dict[str, Any] | None:
		statement = select(CommunityRole).where(CommunityRole.name == name)
		role = await self._session.scalar(statement)
		return self._role_payload(role) if role is not None else None

	async def list_roles(self) -> list[dict[str, Any]]:
		statement = select(CommunityRole).order_by(CommunityRole.name.asc())
		return [self._role_payload(row) for row in (await self._session.scalars(statement)).all()]

	async def get_permissions_for_role(self, role_id: UUID) -> list[str]:
		role = await self._get_role(role_id)
		return [] if role is None else role.permission_names

	async def add_member(self, data: dict[str, Any]) -> dict[str, Any]:
		member = CommunityMember(**data)
		self._session.add(member)
		await self._session.flush()
		return self._member_payload(member)

	async def update_member_role(
		self,
		*,
		user_id: UUID,
		community_id: UUID,
		role_id: UUID,
	) -> dict[str, Any] | None:
		member = await self._get_member(user_id, community_id)
		if member is None:
			return None

		member.role_id = role_id
		await self._session.flush()
		return self._member_payload(member)

	async def remove_member(self, user_id: UUID, community_id: UUID) -> bool:
		member = await self._get_member(user_id, community_id)
		if member is None:
			return False

		await self._session.delete(member)
		await self._session.flush()
		return True

	async def _get_member(self, user_id: UUID, community_id: UUID) -> CommunityMember | None:
		statement = select(CommunityMember).where(
			CommunityMember.user_id == user_id,
			CommunityMember.community_id == community_id,
		)
		return await self._session.scalar(statement)

	async def get_member(self, user_id: UUID, community_id: UUID) -> dict[str, Any] | None:
		member = await self._get_member(user_id, community_id)
		return self._member_payload(member) if member is not None else None

	async def get_member_permissions(self, user_id: UUID, community_id: UUID) -> list[str]:
		statement = (
			select(CommunityRole)
			.join(CommunityMember, CommunityMember.role_id == CommunityRole.id)
			.where(
				CommunityMember.user_id == user_id,
				CommunityMember.community_id == community_id,
			)
		)
		roles = list((await self._session.scalars(statement)).all())
		return sorted({permission for role in roles for permission in role.permission_names})

	async def get_communities_for_user(self, user_id: UUID) -> list[dict[str, Any]]:
		statement = (
			select(Community)
			.join(CommunityMember, CommunityMember.community_id == Community.id)
			.where(CommunityMember.user_id == user_id)
			.order_by(Community.created_at.desc())
		)
		return [self._community_payload(row) for row in (await self._session.scalars(statement)).all()]

	async def list_members(self, community_id: UUID) -> list[dict[str, Any]]:
		statement = (
			select(CommunityMember)
			.where(CommunityMember.community_id == community_id)
			.order_by(CommunityMember.joined_at.asc())
		)
		return [self._member_payload(row) for row in (await self._session.scalars(statement)).all()]

	async def get_owner_id(self, community_id: UUID) -> UUID | None:
		statement = select(Community.owner_id).where(Community.id == community_id)
		return await self._session.scalar(statement)

	async def list_member_ids(self, community_id: UUID) -> list[UUID]:
		statement = (
			select(CommunityMember.user_id)
			.where(CommunityMember.community_id == community_id)
			.order_by(CommunityMember.joined_at.asc())
		)
		return list((await self._session.scalars(statement)).all())


__all__ = ["CommunityRepository"]
