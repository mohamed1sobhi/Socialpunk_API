from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admins.models.models import Role
from app.shared.database.session import AsyncSessionLocal, engine


DEFAULT_ROLES: tuple[dict[str, str | bool], ...] = (
	{
		"name": "super_admin",
		"description": "Full access to the admins boundary.",
		"can_manage_system_users": True,
		"can_read_system_users": True,
		"can_manage_roles": True,
		"can_read_system_permissions": True,
	},
)


async def _get_role_by_name(session: AsyncSession, name: str) -> Role | None:
	statement = select(Role).where(Role.name == name)
	return await session.scalar(statement)


async def seed_admins(session: AsyncSession) -> None:
	created_roles = 0

	for role_seed in DEFAULT_ROLES:
		role = await _get_role_by_name(session, str(role_seed["name"]))
		if role is None:
			role = Role(
				id=uuid4(),
				name=str(role_seed["name"]),
				description=str(role_seed["description"]),
				can_manage_system_users=bool(role_seed["can_manage_system_users"]),
				can_read_system_users=bool(role_seed["can_read_system_users"]),
				can_manage_roles=bool(role_seed["can_manage_roles"]),
				can_read_system_permissions=bool(role_seed["can_read_system_permissions"]),
			)
			session.add(role)
			await session.flush()
			created_roles += 1

	print(f"Seeded admins reference data (roles created: {created_roles}).")


async def main() -> None:
	session = AsyncSessionLocal()
	try:
		await seed_admins(session)
		await session.commit()
	except Exception:
		await session.rollback()
		raise
	finally:
		await session.close()
		await engine.dispose()


if __name__ == "__main__":
	asyncio.run(main())
