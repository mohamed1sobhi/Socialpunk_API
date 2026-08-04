from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from app.shared.events.bus import bus
from app.shared.events.events import MemberJoinedEvent, MemberLeftEvent
from app.shared.exceptions.handlers import ConflictError, ForbiddenError, NotFoundError, ValidationError


COMMUNITY_OWNER_ROLE_NAME = "owner"
COMMUNITY_MEMBER_ROLE_NAME = "member"
COMMUNITY_MEMBERS_MANAGE_PERMISSION = "communities.members.manage"


class CommunityRepositoryProtocol(Protocol):
	async def get_by_id(self, community_id: UUID) -> Any | None: ...
	async def list_public(self) -> list[Any]: ...
	async def list_accessible_ids(self, viewer_id: UUID | None) -> list[UUID]: ...
	async def create_community(self, data: dict[str, Any]) -> Any: ...
	async def add_member(self, data: dict[str, Any]) -> Any: ...
	async def remove_member(self, user_id: UUID, community_id: UUID) -> bool: ...
	async def get_member(self, user_id: UUID, community_id: UUID) -> Any | None: ...
	async def get_role_by_id(self, role_id: UUID) -> Any | None: ...
	async def get_role_by_name(self, name: str) -> Any | None: ...
	async def list_roles(self) -> list[Any]: ...
	async def list_permissions(self) -> list[Any]: ...
	async def get_permissions_for_role(self, role_id: UUID) -> list[str]: ...
	async def update_member_role(
		self,
		*,
		user_id: UUID,
		community_id: UUID,
		role_id: UUID,
	) -> Any | None: ...
	async def get_member_permissions(self, user_id: UUID, community_id: UUID) -> list[str]: ...
	async def get_communities_for_user(self, user_id: UUID) -> list[Any]: ...
	async def list_members(self, community_id: UUID) -> list[Any]: ...
	async def list_member_ids(self, community_id: UUID) -> list[UUID]: ...


class UsersClientProtocol(Protocol):
	async def get_user(self, user_id: UUID | str) -> dict[str, Any]: ...


class CommunityService:
	def __init__(self, repo: CommunityRepositoryProtocol, users_client: UsersClientProtocol) -> None:
		self._repo = repo
		self._users_client = users_client

	async def create_community(self, owner_id: UUID | str, data: dict[str, Any]) -> dict[str, Any]:
		normalized_owner_id = self._parse_uuid(owner_id, label="owner id")
		await self._require_active_user(normalized_owner_id)

		community = await self._repo.create_community(
			{
				"id": uuid4(),
				"name": self._normalize_name(data.get("name"), label="community name"),
				"description": self._normalize_optional_text(data.get("description"), label="community description"),
				"visibility": self._normalize_visibility(data.get("visibility")),
				"owner_id": normalized_owner_id,
			}
		)

		owner_role = await self._repo.get_role_by_name(COMMUNITY_OWNER_ROLE_NAME)
		if owner_role is None:
			raise NotFoundError("Seeded owner role not found")

		await self._repo.add_member(
			{
				"id": uuid4(),
				"user_id": normalized_owner_id,
				"community_id": community.id,
				"role_id": owner_role.id,
			}
		)

		return self._community_to_payload(community)

	async def list_public_communities(self) -> dict[str, Any]:
		communities = await self._repo.list_public()
		return {"communities": [self._community_to_payload(community) for community in communities]}

	async def get_access(
		self,
		community_id: UUID | str,
		viewer_id: UUID | str | None,
	) -> dict[str, Any]:
		normalized_community_id = self._parse_uuid(community_id, label="community id")
		normalized_viewer_id = self._parse_optional_uuid(viewer_id, label="viewer id")
		community = await self._require_existing_community(normalized_community_id)

		is_member = False
		if normalized_viewer_id is not None:
			is_member = await self._repo.get_member(normalized_viewer_id, normalized_community_id) is not None

		can_view = self._coerce_visibility(community.visibility) == "public"
		if normalized_viewer_id is not None:
			can_view = can_view or community.owner_id == normalized_viewer_id or is_member

		return {
			"community_id": normalized_community_id,
			"can_view": can_view,
			"is_member": is_member,
		}

	async def list_accessible_community_ids(self, viewer_id: UUID | str | None) -> dict[str, Any]:
		normalized_viewer_id = self._parse_optional_uuid(viewer_id, label="viewer id")
		community_ids = await self._repo.list_accessible_ids(normalized_viewer_id)
		return {"community_ids": community_ids}

	async def list_roles(self) -> dict[str, Any]:
		roles = await self._repo.list_roles()
		role_payloads: list[dict[str, Any]] = []
		for role in roles:
			permission_names = await self._repo.get_permissions_for_role(role.id)
			role_payloads.append(self._role_to_payload(role, permission_names))
		return {"roles": role_payloads}

	async def list_permissions(self) -> dict[str, Any]:
		permissions = await self._repo.list_permissions()
		return {"permissions": [self._permission_to_payload(permission) for permission in permissions]}

	async def get_community(self, community_id: UUID | str, viewer_id: UUID | str) -> dict[str, Any]:
		normalized_community_id = self._parse_uuid(community_id, label="community id")
		normalized_viewer_id = self._parse_uuid(viewer_id, label="viewer id")

		community = await self._require_existing_community(normalized_community_id)
		await self._enforce_visibility(community, normalized_viewer_id)
		return self._community_to_payload(community)

	async def join_community(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_community_id = self._parse_uuid(community_id, label="community id")

		await self._require_active_user(normalized_user_id)
		community = await self._require_existing_community(normalized_community_id)

		if await self._repo.get_member(normalized_user_id, normalized_community_id):
			raise ConflictError("User is already a member of this community")

		if self._coerce_visibility(community.visibility) == "private":
			raise ForbiddenError("Private communities require an invitation or approval flow")

		member_role = await self._repo.get_role_by_name(COMMUNITY_MEMBER_ROLE_NAME)
		if member_role is None:
			raise NotFoundError("Seeded member role not found")

		member = await self._repo.add_member(
			{
				"id": uuid4(),
				"user_id": normalized_user_id,
				"community_id": normalized_community_id,
				"role_id": member_role.id,
			}
		)

		await bus.publish(
			MemberJoinedEvent(
				user_id=str(normalized_user_id),
				community_id=str(normalized_community_id),
			)
		)
		return self._member_to_payload(member)

	async def leave_community(self, user_id: UUID | str, community_id: UUID | str) -> None:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_community_id = self._parse_uuid(community_id, label="community id")

		await self._require_active_user(normalized_user_id)
		community = await self._require_existing_community(normalized_community_id)

		member = await self._repo.get_member(normalized_user_id, normalized_community_id)
		if member is None:
			raise NotFoundError("Community membership not found")

		if community.owner_id == normalized_user_id:
			raise ForbiddenError("Community owners cannot leave without transferring ownership first")

		removed = await self._repo.remove_member(normalized_user_id, normalized_community_id)
		if not removed:
			raise NotFoundError("Community membership not found")

		await bus.publish(
			MemberLeftEvent(
				user_id=str(normalized_user_id),
				community_id=str(normalized_community_id),
			)
		)

	async def require_community_permission(
		self,
		user_id: UUID | str,
		community_id: UUID | str,
		permission: str,
	) -> None:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_community_id = self._parse_uuid(community_id, label="community id")
		normalized_permission = permission.strip()

		if not normalized_permission:
			raise ValidationError("Permission name must not be empty")

		community = await self._require_existing_community(normalized_community_id)
		if community.owner_id == normalized_user_id:
			return

		member = await self._repo.get_member(normalized_user_id, normalized_community_id)
		if member is None:
			raise ForbiddenError("Community membership is required")

		permissions = await self._repo.get_member_permissions(normalized_user_id, normalized_community_id)
		if normalized_permission not in permissions:
			raise ForbiddenError("You do not have the required community permission")

	async def list_members(self, requester_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		normalized_requester_id = self._parse_uuid(requester_id, label="requester id")
		normalized_community_id = self._parse_uuid(community_id, label="community id")

		community = await self._require_existing_community(normalized_community_id)
		await self._enforce_visibility(community, normalized_requester_id)

		members = await self._repo.list_members(normalized_community_id)
		return {
			"community_id": normalized_community_id,
			"members": [self._member_to_payload(member) for member in members],
		}

	async def assign_role_to_member(
		self,
		community_id: UUID | str,
		member_user_id: UUID | str,
		role_id: UUID | str,
	) -> dict[str, Any]:
		normalized_community_id = self._parse_uuid(community_id, label="community id")
		normalized_member_user_id = self._parse_uuid(member_user_id, label="member user id")
		normalized_role_id = self._parse_uuid(role_id, label="role id")

		await self._require_active_user(normalized_member_user_id)
		community = await self._require_existing_community(normalized_community_id)

		member = await self._repo.get_member(normalized_member_user_id, normalized_community_id)
		if member is None:
			raise NotFoundError("Community membership not found")

		role = await self._repo.get_role_by_id(normalized_role_id)
		if role is None:
			raise NotFoundError("Community role not found")

		if community.owner_id == normalized_member_user_id and role.name != COMMUNITY_OWNER_ROLE_NAME:
			raise ForbiddenError("The community owner role cannot be changed")

		if community.owner_id != normalized_member_user_id and role.name == COMMUNITY_OWNER_ROLE_NAME:
			raise ValidationError("The owner role is reserved for the community owner")

		updated_member = await self._repo.update_member_role(
			user_id=normalized_member_user_id,
			community_id=normalized_community_id,
			role_id=normalized_role_id,
		)
		if updated_member is None:
			raise NotFoundError("Community membership not found")
		return self._member_to_payload(updated_member)

	async def get_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_community_id = self._parse_uuid(community_id, label="community id")

		await self._require_existing_community(normalized_community_id)
		member = await self._repo.get_member(normalized_user_id, normalized_community_id)
		if member is None:
			raise NotFoundError("Community membership not found")
		return self._member_to_payload(member)

	async def is_member(self, user_id: UUID | str, community_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_community_id = self._parse_uuid(community_id, label="community id")

		await self._require_existing_community(normalized_community_id)
		member = await self._repo.get_member(normalized_user_id, normalized_community_id)
		return {
			"community_id": normalized_community_id,
			"user_id": normalized_user_id,
			"is_member": member is not None,
		}

	async def get_owner(self, community_id: UUID | str) -> dict[str, Any]:
		normalized_community_id = self._parse_uuid(community_id, label="community id")
		community = await self._require_existing_community(normalized_community_id)
		return {
			"community_id": normalized_community_id,
			"owner_id": community.owner_id,
		}

	async def list_member_ids(self, community_id: UUID | str) -> dict[str, Any]:
		normalized_community_id = self._parse_uuid(community_id, label="community id")
		await self._require_existing_community(normalized_community_id)
		member_ids = await self._repo.list_member_ids(normalized_community_id)
		return {
			"community_id": normalized_community_id,
			"member_ids": member_ids,
		}

	async def list_user_communities(self, user_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		communities = await self._repo.get_communities_for_user(normalized_user_id)
		return {
			"user_id": normalized_user_id,
			"communities": [self._community_to_payload(community) for community in communities],
		}

	async def _require_active_user(self, user_id: UUID) -> dict[str, Any]:
		user = await self._users_client.get_user(user_id)
		if not user.get("is_active", False):
			raise ValidationError("User is not active")
		return user

	async def _require_existing_community(self, community_id: UUID) -> Any:
		community = await self._repo.get_by_id(community_id)
		if community is None:
			raise NotFoundError("Community not found")
		return community

	async def _enforce_visibility(self, community: Any, viewer_id: UUID) -> None:
		if self._coerce_visibility(community.visibility) != "private":
			return

		if community.owner_id == viewer_id:
			return

		member = await self._repo.get_member(viewer_id, community.id)
		if member is None:
			raise ForbiddenError("Private community membership is required")

	def _community_to_payload(self, community: Any) -> dict[str, Any]:
		return {
			"id": community.id,
			"name": community.name,
			"description": community.description,
			"visibility": self._coerce_visibility(community.visibility),
			"owner_id": community.owner_id,
			"created_at": community.created_at,
		}

	def _member_to_payload(self, member: Any) -> dict[str, Any]:
		return {
			"id": member.id,
			"user_id": member.user_id,
			"community_id": member.community_id,
			"role_id": member.role_id,
			"joined_at": member.joined_at,
		}

	def _role_to_payload(self, role: Any, permission_names: list[str]) -> dict[str, Any]:
		return {
			"id": role.id,
			"name": role.name,
			"permission_names": permission_names,
		}

	def _permission_to_payload(self, permission: Any) -> dict[str, Any]:
		return {
			"id": permission.id,
			"name": permission.name,
		}

	def _parse_uuid(self, value: UUID | str, *, label: str) -> UUID:
		if isinstance(value, UUID):
			return value

		try:
			return UUID(value)
		except (TypeError, ValueError) as exc:
			raise ValidationError(f"Invalid {label}") from exc

	def _parse_optional_uuid(self, value: UUID | str | None, *, label: str) -> UUID | None:
		if value is None:
			return None
		return self._parse_uuid(value, label=label)

	def _normalize_name(self, value: Any, *, label: str) -> str:
		if not isinstance(value, str):
			raise ValidationError(f"{label.capitalize()} must be a string")

		normalized_value = value.strip()
		if not normalized_value:
			raise ValidationError(f"{label.capitalize()} must not be empty")
		return normalized_value

	def _normalize_optional_text(self, value: Any, *, label: str) -> str | None:
		if value is None:
			return None
		if not isinstance(value, str):
			raise ValidationError(f"{label.capitalize()} must be a string or null")

		normalized_value = value.strip()
		return normalized_value or None

	def _normalize_visibility(self, value: Any) -> str:
		visibility = self._coerce_visibility(value)
		if visibility not in {"public", "private"}:
			raise ValidationError("Visibility must be either 'public' or 'private'")
		return visibility

	def _coerce_visibility(self, value: Any) -> str:
		if isinstance(value, str):
			return value

		coerced_value = getattr(value, "value", None)
		if isinstance(coerced_value, str):
			return coerced_value

		raise ValidationError("Invalid community visibility")


__all__ = [
	"COMMUNITY_MEMBER_ROLE_NAME",
	"COMMUNITY_MEMBERS_MANAGE_PERMISSION",
	"COMMUNITY_OWNER_ROLE_NAME",
	"CommunityService",
]
