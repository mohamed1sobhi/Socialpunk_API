from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from app.shared.auth.jwt import (
	create_access_token,
	create_refresh_token,
	decode_token,
	hash_password,
	verify_password,
)
from app.shared.events.bus import bus
from app.shared.events.events import UserRegisteredEvent
from app.shared.exceptions.handlers import ConflictError, NotFoundError, UnauthorizedError, ValidationError


class UserRepositoryProtocol(Protocol):
	async def get_by_id(self, user_id: UUID) -> Any | None: ...
	async def get_by_email(self, email: str) -> Any | None: ...
	async def get_by_username(self, username: str) -> Any | None: ...
	async def create(self, data: dict[str, Any]) -> Any: ...
	async def update_user(self, user_id: UUID, data: dict[str, Any]) -> Any | None: ...
	async def deactivate_user(self, user_id: UUID) -> Any | None: ...
	async def get_profile(self, user_id: UUID) -> Any | None: ...
	async def upsert_profile(self, user_id: UUID, data: dict[str, Any]) -> Any: ...


class UserService:
	def __init__(self, repo: UserRepositoryProtocol) -> None:
		self._repo = repo

	async def register(self, *, username: str, email: str, password: str) -> dict[str, Any]:
		normalized_username = self._normalize_username(username)
		normalized_email = self._normalize_email(email)
		self._validate_password(password)

		if await self._repo.get_by_username(normalized_username):
			raise ConflictError("Username is already in use")
		if await self._repo.get_by_email(normalized_email):
			raise ConflictError("Email is already in use")

		user_id = uuid4()
		user = await self._repo.create(
			{
				"id": user_id,
				"username": normalized_username,
				"email": normalized_email,
				"hashed_password": hash_password(password),
				"is_active": True,
			}
		)
		await self._repo.upsert_profile(
			user_id,
			{
				"id": uuid4(),
				"display_name": None,
				"bio": None,
				"avatar_url": None,
			},
		)

		await bus.publish(UserRegisteredEvent(user_id=str(user.id), username=user.username))
		return self._user_to_payload(user)

	async def login(self, *, email: str, password: str) -> dict[str, str]:
		normalized_email = self._normalize_email(email)
		user = await self._repo.get_by_email(normalized_email)
		if user is None or not getattr(user, "is_active", False):
			raise UnauthorizedError("Invalid email or password")
		if not verify_password(password, getattr(user, "hashed_password", "")):
			raise UnauthorizedError("Invalid email or password")

		return self._token_pair(user.id)

	async def refresh_tokens(self, *, refresh_token: str) -> dict[str, str]:
		payload = decode_token(refresh_token)
		subject = payload.get("sub")
		token_type = payload.get("token_type")

		if not isinstance(subject, str) or not subject:
			raise UnauthorizedError("Invalid token payload")
		if token_type != "refresh":
			raise UnauthorizedError("Refresh token required")

		user = await self._repo.get_by_id(self._parse_user_id(subject))
		if user is None or not getattr(user, "is_active", False):
			raise UnauthorizedError("User is not available")

		return self._token_pair(user.id)

	async def get_user(self, user_id: UUID | str) -> dict[str, Any]:
		user = await self._repo.get_by_id(self._parse_user_id(user_id))
		if user is None:
			raise NotFoundError("User not found")
		return self._user_to_payload(user)

	async def get_profile(self, user_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_user_id(user_id)
		await self._require_existing_user(normalized_user_id)

		profile = await self._repo.get_profile(normalized_user_id)
		if profile is None:
			raise NotFoundError("Profile not found")
		return self._profile_to_payload(profile)

	async def update_user(self, user_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
		normalized_user_id = self._parse_user_id(user_id)
		current_user = await self._require_existing_user(normalized_user_id)

		updates: dict[str, Any] = {}
		if "username" in data:
			username = data.get("username")
			if not isinstance(username, str):
				raise ValidationError("Username must be a string")

			normalized_username = self._normalize_username(username)
			existing_user = await self._repo.get_by_username(normalized_username)
			if existing_user is not None and existing_user.id != current_user.id:
				raise ConflictError("Username is already in use")
			updates["username"] = normalized_username

		if "email" in data:
			email = data.get("email")
			if not isinstance(email, str):
				raise ValidationError("Email must be a string")

			normalized_email = self._normalize_email(email)
			existing_user = await self._repo.get_by_email(normalized_email)
			if existing_user is not None and existing_user.id != current_user.id:
				raise ConflictError("Email is already in use")
			updates["email"] = normalized_email

		if not updates:
			raise ValidationError("At least one account field must be provided")

		updated_user = await self._repo.update_user(normalized_user_id, updates)
		if updated_user is None:
			raise NotFoundError("User not found")
		return self._user_to_payload(updated_user)

	async def update_profile(self, user_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
		normalized_user_id = self._parse_user_id(user_id)
		await self._require_existing_user(normalized_user_id)

		updates: dict[str, Any] = {}
		for field_name in ("display_name", "bio", "avatar_url"):
			if field_name in data:
				updates[field_name] = self._normalize_optional_text(data[field_name])

		if not updates:
			raise ValidationError("At least one profile field must be provided")

		profile = await self._repo.get_profile(normalized_user_id)
		if profile is None:
			updates["id"] = uuid4()

		updated_profile = await self._repo.upsert_profile(normalized_user_id, updates)
		return self._profile_to_payload(updated_profile)

	async def delete_user(self, user_id: UUID | str) -> None:
		normalized_user_id = self._parse_user_id(user_id)
		deactivated_user = await self._repo.deactivate_user(normalized_user_id)
		if deactivated_user is None:
			raise NotFoundError("User not found")

	async def _require_existing_user(self, user_id: UUID) -> Any:
		user = await self._repo.get_by_id(user_id)
		if user is None:
			raise NotFoundError("User not found")
		return user

	def _token_pair(self, user_id: UUID) -> dict[str, str]:
		return {
			"access_token": create_access_token(user_id),
			"refresh_token": create_refresh_token(user_id),
			"token_type": "bearer",
		}

	def _parse_user_id(self, user_id: UUID | str) -> UUID:
		if isinstance(user_id, UUID):
			return user_id
		try:
			return UUID(user_id)
		except (TypeError, ValueError) as exc:
			raise ValidationError("Invalid user id") from exc

	def _normalize_email(self, email: str) -> str:
		normalized_email = email.strip().lower()
		if not normalized_email:
			raise ValidationError("Email must not be empty")
		return normalized_email

	def _normalize_username(self, username: str) -> str:
		normalized_username = username.strip()
		if not normalized_username:
			raise ValidationError("Username must not be empty")
		return normalized_username

	def _validate_password(self, password: str) -> None:
		if len(password) < 8:
			raise ValidationError("Password must be at least 8 characters long")

	def _normalize_optional_text(self, value: Any) -> str | None:
		if value is None:
			return None
		if not isinstance(value, str):
			raise ValidationError("Profile fields must be strings or null")
		normalized_value = value.strip()
		return normalized_value or None

	def _user_to_payload(self, user: Any) -> dict[str, Any]:
		return {
			"id": user.id,
			"username": user.username,
			"email": user.email,
			"is_active": user.is_active,
			"created_at": user.created_at,
		}

	def _profile_to_payload(self, profile: Any) -> dict[str, Any]:
		return {
			"id": profile.id,
			"user_id": profile.user_id,
			"display_name": profile.display_name,
			"bio": profile.bio,
			"avatar_url": profile.avatar_url,
			"updated_at": profile.updated_at,
		}


__all__ = ["UserService"]
