from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from app.shared.events.bus import bus
from app.shared.events.events import FriendRequestSentEvent, FriendshipFormedEvent
from app.shared.exceptions.handlers import ConflictError, ForbiddenError, NotFoundError, ValidationError


class SocialGraphRepositoryProtocol(Protocol):
	async def get_friendship(self, user_a: UUID, user_b: UUID) -> dict[str, Any] | None: ...
	async def get_request_by_id(self, request_id: UUID) -> dict[str, Any] | None: ...
	async def get_pending_request_for_pair(self, user_a: UUID, user_b: UUID) -> dict[str, Any] | None: ...
	async def create_request(
		self,
		*,
		request_id: UUID,
		requester_id: UUID,
		receiver_id: UUID,
	) -> dict[str, Any]: ...
	async def reject_request(self, request_id: UUID) -> dict[str, Any] | None: ...
	async def create_friendship(self, user_a: UUID, user_b: UUID) -> dict[str, Any]: ...
	async def delete_request(self, request_id: UUID) -> None: ...
	async def get_friends(self, user_id: UUID) -> list[UUID]: ...
	async def get_pending_requests(self, user_id: UUID) -> list[dict[str, Any]]: ...


class UsersClientProtocol(Protocol):
	async def get_user(self, user_id: UUID | str) -> dict[str, Any]: ...


class SocialGraphService:
	def __init__(self, repo: SocialGraphRepositoryProtocol, users_client: UsersClientProtocol) -> None:
		self._repo = repo
		self._users_client = users_client

	async def send_request(self, requester_id: UUID | str, receiver_id: UUID | str) -> dict[str, Any]:
		normalized_requester_id = self._parse_uuid(requester_id, label="requester id")
		normalized_receiver_id = self._parse_uuid(receiver_id, label="receiver id")

		if normalized_requester_id == normalized_receiver_id:
			raise ValidationError("You cannot send a friend request to yourself")

		await self._require_active_user(normalized_requester_id)
		await self._require_active_user(normalized_receiver_id)

		if await self._repo.get_friendship(normalized_requester_id, normalized_receiver_id):
			raise ConflictError("Users are already friends")

		if await self._repo.get_pending_request_for_pair(normalized_requester_id, normalized_receiver_id):
			raise ConflictError("A pending friend request already exists for this pair")

		friend_request = await self._repo.create_request(
			request_id=uuid4(),
			requester_id=normalized_requester_id,
			receiver_id=normalized_receiver_id,
		)

		await bus.publish(
			FriendRequestSentEvent(
				requester_id=str(friend_request["requester_id"]),
				receiver_id=str(friend_request["receiver_id"]),
			)
		)
		return self._friend_request_to_payload(friend_request)

	async def respond_to_request(
		self,
		responder_id: UUID | str,
		request_id: UUID | str,
		*,
		accept: bool,
	) -> dict[str, Any]:
		normalized_responder_id = self._parse_uuid(responder_id, label="responder id")
		normalized_request_id = self._parse_uuid(request_id, label="request id")

		await self._require_active_user(normalized_responder_id)

		friend_request = await self._repo.get_request_by_id(normalized_request_id)
		if friend_request is None:
			raise NotFoundError("Friend request not found")

		if friend_request["status"] != "pending":
			raise ValidationError("Friend request is no longer pending")

		if friend_request["receiver_id"] != normalized_responder_id:
			raise ForbiddenError("Only the recipient can respond to this friend request")

		if accept:
			await self._require_active_user(friend_request["requester_id"])

			if await self._repo.get_friendship(friend_request["requester_id"], friend_request["receiver_id"]):
				raise ConflictError("Users are already friends")

			friendship = await self._repo.create_friendship(
				friend_request["requester_id"],
				friend_request["receiver_id"],
			)
			await self._repo.delete_request(friend_request["id"])

			await bus.publish(
				FriendshipFormedEvent(
					user_low=str(friendship["user_low"]),
					user_high=str(friendship["user_high"]),
				)
			)
			return self._friendship_to_payload(friendship)

		rejected_request = await self._repo.reject_request(friend_request["id"])
		if rejected_request is None:
			raise NotFoundError("Friend request not found")
		return self._friend_request_to_payload(rejected_request)

	async def get_friends(self, user_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		await self._require_active_user(normalized_user_id)

		friend_ids = await self._repo.get_friends(normalized_user_id)
		return {
			"user_id": normalized_user_id,
			"friend_ids": friend_ids,
		}

	async def get_pending_requests(self, user_id: UUID | str) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		await self._require_active_user(normalized_user_id)

		friend_requests = await self._repo.get_pending_requests(normalized_user_id)
		return {
			"user_id": normalized_user_id,
			"requests": [self._friend_request_to_payload(friend_request) for friend_request in friend_requests],
		}

	async def _require_active_user(self, user_id: UUID) -> dict[str, Any]:
		user = await self._users_client.get_user(user_id)
		if not user.get("is_active", False):
			raise ValidationError("User is not active")
		return user

	def _friend_request_to_payload(self, friend_request: dict[str, Any]) -> dict[str, Any]:
		return dict(friend_request)

	def _friendship_to_payload(self, friendship: dict[str, Any]) -> dict[str, Any]:
		return dict(friendship)

	def _parse_uuid(self, value: UUID | str, *, label: str) -> UUID:
		if isinstance(value, UUID):
			return value

		try:
			return UUID(value)
		except (TypeError, ValueError) as exc:
			raise ValidationError(f"Invalid {label}") from exc


__all__ = ["SocialGraphService"]
