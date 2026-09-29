from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models.models import User, UserProfile


class UserRepository:
	def __init__(self, session: AsyncSession) -> None:
		self._session = session

	@staticmethod
	def _user_payload(user: User) -> dict[str, Any]:
		return {field: getattr(user, field) for field in (
			"id", "username", "email", "hashed_password", "is_active", "created_at",
		)}

	@staticmethod
	def _profile_payload(profile: UserProfile) -> dict[str, Any]:
		return {field: getattr(profile, field) for field in (
			"id", "user_id", "display_name", "bio", "avatar_url", "updated_at",
		)}

	async def _get_user(self, user_id: UUID) -> User | None:
		statement = select(User).where(User.id == user_id)
		return await self._session.scalar(statement)

	async def get_by_id(self, user_id: UUID) -> dict[str, Any] | None:
		user = await self._get_user(user_id)
		return self._user_payload(user) if user is not None else None

	async def get_by_email(self, email: str) -> dict[str, Any] | None:
		statement = select(User).where(User.email == email)
		user = await self._session.scalar(statement)
		return self._user_payload(user) if user is not None else None

	async def get_by_username(self, username: str) -> dict[str, Any] | None:
		statement = select(User).where(User.username == username)
		user = await self._session.scalar(statement)
		return self._user_payload(user) if user is not None else None

	async def create(self, data: dict[str, Any]) -> dict[str, Any]:
		user = User(**data)
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

	async def _get_profile(self, user_id: UUID) -> UserProfile | None:
		statement = select(UserProfile).where(UserProfile.user_id == user_id)
		return await self._session.scalar(statement)

	async def get_profile(self, user_id: UUID) -> dict[str, Any] | None:
		profile = await self._get_profile(user_id)
		return self._profile_payload(profile) if profile is not None else None

	async def upsert_profile(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
		profile = await self._get_profile(user_id)

		if profile is None:
			profile = UserProfile(user_id=user_id, **data)
			self._session.add(profile)
		else:
			for field_name, value in data.items():
				setattr(profile, field_name, value)
			profile.updated_at = datetime.now(timezone.utc)

		await self._session.flush()
		return self._profile_payload(profile)


__all__ = ["UserRepository"]
