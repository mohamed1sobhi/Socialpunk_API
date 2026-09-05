from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.communities.models.models import CommunityRole
from app.shared.database.session import AsyncSessionLocal, engine


DEFAULT_ROLES: tuple[dict[str, str | bool], ...] = (
	{
		"name": "owner",
		"can_manage_members": True,
		"can_read_roles": True,
	},
	{
		"name": "member",
		"can_manage_members": False,
		"can_read_roles": True,
	},
)


async def _get_role_by_name(session: AsyncSession, name: str) -> CommunityRole | None:
	statement = select(CommunityRole).where(CommunityRole.name == name)
	return await session.scalar(statement)


async def seed_communities(session: AsyncSession) -> None:
	created_roles = 0

	for role_seed in DEFAULT_ROLES:
		role = await _get_role_by_name(session, str(role_seed["name"]))
		if role is None:
			role = CommunityRole(
				id=uuid4(),
				name=str(role_seed["name"]),
				can_manage_members=bool(role_seed["can_manage_members"]),
				can_read_roles=bool(role_seed["can_read_roles"]),
			)
			session.add(role)
			await session.flush()
			created_roles += 1

	print(f"Seeded communities reference data (roles created: {created_roles}).")


async def main() -> None:
	session = AsyncSessionLocal()
	try:
		await seed_communities(session)
		await session.commit()
	except Exception:
		await session.rollback()
		raise
	finally:
		await session.close()
		await engine.dispose()


if __name__ == "__main__":
	asyncio.run(main())
