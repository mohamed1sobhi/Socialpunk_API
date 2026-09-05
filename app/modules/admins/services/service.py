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
from app.shared.exceptions.handlers import ConflictError, NotFoundError, UnauthorizedError, ValidationError


ROLE_PERMISSION_FIELDS = (
	"can_manage_system_users",
	"can_read_system_users",
	"can_manage_roles",
	"can_read_system_permissions",
)


class AdminRepositoryProtocol(Protocol):
	async def get_user_by_id(self, user_id: UUID) -> Any | None: ...
	async def get_user_by_email(self, email: str) -> Any | None: ...
	async def get_user_by_username(self, username: str) -> Any | None: ...
	async def create_user(self, data: dict[str, Any]) -> Any: ...
	async def update_user(self, user_id: UUID, data: dict[str, Any]) -> Any | None: ...
	async def deactivate_user(self, user_id: UUID) -> Any | None: ...
	async def get_role_by_id(self, role_id: UUID) -> Any | None: ...
	async def get_role_by_name(self, name: str) -> Any | None: ...
	async def list_roles(self) -> list[Any]: ...
	async def create_role(self, data: dict[str, Any]) -> Any: ...
	async def update_role(self, role_id: UUID, data: dict[str, Any]) -> Any | None: ...
	async def get_user_role(self, user_id: UUID, role_id: UUID) -> Any | None: ...
	async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> Any: ...
	async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> bool: ...
	async def get_user_roles(self, user_id: UUID) -> list[Any]: ...
	async def get_user_permissions(self, user_id: UUID) -> list[str]: ...


class AdminService:
	def __init__(self, repo: AdminRepositoryProtocol) -> None:
		self._repo = repo

	async def login(self, *, email: str, password: str) -> dict[str, str]:
		normalized_email = self._normalize_email(email)
		user = await self._repo.get_user_by_email(normalized_email)
		if user is None or not getattr(user, "is_active", False):
			raise UnauthorizedError("Invalid email or password")
		if not verify_password(password, getattr(user, "hashed_password", "")):
			raise UnauthorizedError("Invalid email or password")

		permissions = await self._repo.get_user_permissions(user.id)
		return self._token_pair(user.id, permissions)

	async def refresh_tokens(self, *, refresh_token: str) -> dict[str, str]:
		payload = decode_token(refresh_token)
		subject = payload.get("sub")
		token_type = payload.get("token_type")

		if not isinstance(subject, str) or not subject:
			raise UnauthorizedError("Invalid token payload")
		if token_type != "refresh":
			raise UnauthorizedError("Refresh token required")

		user = await self._repo.get_user_by_id(self._parse_uuid(subject, label="user id"))
		if user is None or not getattr(user, "is_active", False):
			raise UnauthorizedError("User is not available")

		permissions = await self._repo.get_user_permissions(user.id)
		return self._token_pair(user.id, permissions)

	async def create_system_user(self, data: dict[str, Any], role_names: list[str]) -> dict[str, Any]:
		username = data.get("username")
		email = data.get("email")
		password = data.get("password")

		if not isinstance(username, str):
			raise ValidationError("Username must be provided")
		if not isinstance(email, str):
			raise ValidationError("Email must be provided")
		if not isinstance(password, str):
			raise ValidationError("Password must be provided")

		normalized_username = self._normalize_username(username)
		normalized_email = self._normalize_email(email)
		self._validate_password(password)

		await self._ensure_unique_credentials(normalized_username, normalized_email)
		resolved_roles = await self._resolve_roles_by_name(role_names)

		user = await self._repo.create_user(
			{
				"id": uuid4(),
				"username": normalized_username,
				"email": normalized_email,
				"hashed_password": hash_password(password),
				"is_active": True,
			}
		)

		for role in resolved_roles:
			await self._repo.assign_role_to_user(user.id, role.id)

		return self._system_user_to_payload(user, resolved_roles)

	async def get_system_user(self, user_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		user = await self._require_existing_user(normalized_user_id)
		roles = await self._repo.get_user_roles(normalized_user_id)
		return self._system_user_to_payload(user, roles)

	async def update_system_user(self, user_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		current_user = await self._require_existing_user(normalized_user_id)

		updates: dict[str, Any] = {}
		if "username" in data:
			username = data.get("username")
			if not isinstance(username, str):
				raise ValidationError("Username must be a string")
			normalized_username = self._normalize_username(username)
			existing_user = await self._repo.get_user_by_username(normalized_username)
			if existing_user is not None and existing_user.id != current_user.id:
				raise ConflictError("Username is already in use")
			updates["username"] = normalized_username

		if "email" in data:
			email = data.get("email")
			if not isinstance(email, str):
				raise ValidationError("Email must be a string")
			normalized_email = self._normalize_email(email)
			existing_user = await self._repo.get_user_by_email(normalized_email)
			if existing_user is not None and existing_user.id != current_user.id:
				raise ConflictError("Email is already in use")
			updates["email"] = normalized_email

		if "password" in data:
			password = data.get("password")
			if not isinstance(password, str):
				raise ValidationError("Password must be a string")
			self._validate_password(password)
			updates["hashed_password"] = hash_password(password)

		if not updates:
			raise ValidationError("At least one system-user field must be provided")

		updated_user = await self._repo.update_user(normalized_user_id, updates)
		if updated_user is None:
			raise NotFoundError("System user not found")

		roles = await self._repo.get_user_roles(normalized_user_id)
		return self._system_user_to_payload(updated_user, roles)

	async def deactivate_system_user(self, user_id: UUID | str) -> None:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		deactivated_user = await self._repo.deactivate_user(normalized_user_id)
		if deactivated_user is None:
			raise NotFoundError("System user not found")

	async def assign_role(self, user_id: UUID | str, *, role_name: str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		await self._require_existing_user(normalized_user_id)

		normalized_role_name = self._normalize_name(role_name, label="role name")
		role = await self._repo.get_role_by_name(normalized_role_name)
		if role is None:
			raise NotFoundError("Role not found")

		if await self._repo.get_user_role(normalized_user_id, role.id):
			raise ConflictError("Role is already assigned to the system user")

		user_role = await self._repo.assign_role_to_user(normalized_user_id, role.id)
		return self._role_assignment_to_payload(user_role, role)

	async def revoke_role(self, user_id: UUID | str, role_id: UUID | str) -> None:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_role_id = self._parse_uuid(role_id, label="role id")
		await self._require_existing_user(normalized_user_id)

		role = await self._repo.get_role_by_id(normalized_role_id)
		if role is None:
			raise NotFoundError("Role not found")

		revoked = await self._repo.revoke_role_from_user(normalized_user_id, normalized_role_id)
		if not revoked:
			raise NotFoundError("Role assignment not found")

	async def get_permissions_for_user(self, user_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		await self._require_existing_user(normalized_user_id)

		permissions = await self._repo.get_user_permissions(normalized_user_id)
		return {
			"user_id": normalized_user_id,
			"permissions": permissions,
		}

	async def list_roles(self) -> dict[str, Any]:
		roles = await self._repo.list_roles()
		return {"roles": [self._role_to_payload(role) for role in roles]}

	async def create_role(
		self,
		*,
		name: str,
		description: str | None = None,
		permission_flags: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		normalized_name = self._normalize_name(name, label="role name")
		if await self._repo.get_role_by_name(normalized_name):
			raise ConflictError("Role already exists")

		role_data = {
			"id": uuid4(),
			"name": normalized_name,
			"description": self._normalize_optional_text(description),
		}
		role_data.update({field_name: False for field_name in ROLE_PERMISSION_FIELDS})
		role_data.update(self._normalize_role_permission_flags(permission_flags or {}))
		role = await self._repo.create_role(
			role_data
		)
		return self._role_to_payload(role)

	async def update_role(self, role_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
		normalized_role_id = self._parse_uuid(role_id, label="role id")
		current_role = await self._repo.get_role_by_id(normalized_role_id)
		if current_role is None:
			raise NotFoundError("Role not found")

		updates: dict[str, Any] = {}
		if "name" in data:
			name = self._normalize_name(data.get("name"), label="role name")
			existing_role = await self._repo.get_role_by_name(name)
			if existing_role is not None and existing_role.id != normalized_role_id:
				raise ConflictError("Role already exists")
			updates["name"] = name

		if "description" in data:
			updates["description"] = self._normalize_optional_text(data.get("description"))

		updates.update(
			self._normalize_role_permission_flags(
				{field_name: data[field_name] for field_name in ROLE_PERMISSION_FIELDS if field_name in data}
			)
		)
		if not updates:
			raise ValidationError("At least one role field must be provided")

		updated_role = await self._repo.update_role(normalized_role_id, updates)
		if updated_role is None:
			raise NotFoundError("Role not found")
		return self._role_to_payload(updated_role)

	async def _ensure_unique_credentials(self, username: str, email: str) -> None:
		if await self._repo.get_user_by_username(username):
			raise ConflictError("Username is already in use")
		if await self._repo.get_user_by_email(email):
			raise ConflictError("Email is already in use")

	async def _resolve_roles_by_name(self, role_names: list[str]) -> list[Any]:
		unique_role_names: list[str] = []
		for raw_role_name in role_names:
			if not isinstance(raw_role_name, str):
				raise ValidationError("Role names must be strings")

			normalized_role_name = self._normalize_name(raw_role_name, label="role name")
			if normalized_role_name not in unique_role_names:
				unique_role_names.append(normalized_role_name)

		resolved_roles: list[Any] = []
		for role_name in unique_role_names:
			role = await self._repo.get_role_by_name(role_name)
			if role is None:
				raise NotFoundError(f"Role not found: {role_name}")
			resolved_roles.append(role)

		return resolved_roles

	async def _require_existing_user(self, user_id: UUID) -> Any:
		user = await self._repo.get_user_by_id(user_id)
		if user is None:
			raise NotFoundError("System user not found")
		return user

	def _token_pair(self, user_id: UUID, permissions: list[str]) -> dict[str, str]:
		return {
			"access_token": create_access_token(user_id, permissions),
			"refresh_token": create_refresh_token(user_id),
			"token_type": "bearer",
		}

	def _parse_uuid(self, value: UUID | str, *, label: str) -> UUID:
		if isinstance(value, UUID):
			return value

		try:
			return UUID(value)
		except (TypeError, ValueError) as exc:
			raise ValidationError(f"Invalid {label}") from exc

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

	def _normalize_name(self, value: Any, *, label: str) -> str:
		if not isinstance(value, str):
			raise ValidationError(f"{label.capitalize()} must be a string")

		normalized_value = value.strip()
		if not normalized_value:
			raise ValidationError(f"{label.capitalize()} must not be empty")
		return normalized_value

	def _normalize_optional_text(self, value: Any) -> str | None:
		if value is None:
			return None
		if not isinstance(value, str):
			raise ValidationError("Description must be a string or null")
		normalized_value = value.strip()
		return normalized_value or None

	def _normalize_role_permission_flags(self, values: dict[str, Any]) -> dict[str, bool]:
		flags: dict[str, bool] = {}
		for field_name, value in values.items():
			if field_name not in ROLE_PERMISSION_FIELDS:
				continue
			if not isinstance(value, bool):
				raise ValidationError(f"{field_name} must be a boolean")
			flags[field_name] = value
		return flags

	def _validate_password(self, password: str) -> None:
		if len(password) < 8:
			raise ValidationError("Password must be at least 8 characters long")

	def _system_user_to_payload(self, user: Any, roles: list[Any]) -> dict[str, Any]:
		return {
			"id": user.id,
			"username": user.username,
			"email": user.email,
			"is_active": user.is_active,
			"created_at": user.created_at,
			"role_names": [role.name for role in roles],
		}

	def _role_to_payload(self, role: Any) -> dict[str, Any]:
		return {
			"id": role.id,
			"name": role.name,
			"description": role.description,
			"can_manage_system_users": role.can_manage_system_users,
			"can_read_system_users": role.can_read_system_users,
			"can_manage_roles": role.can_manage_roles,
			"can_read_system_permissions": role.can_read_system_permissions,
		}

	def _role_assignment_to_payload(self, user_role: Any, role: Any) -> dict[str, Any]:
		return {
			"user_id": user_role.user_id,
			"role_id": user_role.role_id,
			"role_name": role.name,
			"assigned_at": user_role.assigned_at,
		}

__all__ = ["AdminService"]
