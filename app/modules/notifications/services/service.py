from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.shared.events.bus import bus
from app.shared.events.events import (
	FriendRequestSentEvent,
	FriendshipFormedEvent,
	MemberJoinedEvent,
	PostCreatedEvent,
)
from app.shared.exceptions.handlers import NotFoundError, ValidationError


class NotificationRepositoryProtocol(Protocol):
	async def create(self, recipient_id: UUID, type: str, payload: dict[str, Any]) -> Any: ...
	async def get_for_user(self, user_id: UUID, limit: int, offset: int) -> list[Any]: ...
	async def mark_read(self, notification_id: UUID, user_id: UUID) -> Any | None: ...
	async def mark_all_read(self, user_id: UUID) -> None: ...
	async def commit(self) -> None: ...
	async def rollback(self) -> None: ...


class WebSocketManagerProtocol(Protocol):
	async def send_to_user(self, user_id: str, payload: Any) -> bool: ...


class EmailClientProtocol(Protocol):
	async def send_email(self, *, to_email: str | None, subject: str, body: str) -> bool: ...


class SMSClientProtocol(Protocol):
	async def send_sms(self, *, to_phone: str | None, body: str) -> bool: ...


class UsersClientProtocol(Protocol):
	async def get_contact(self, user_id: UUID | str) -> dict[str, Any]: ...


class CommunitiesClientProtocol(Protocol):
	async def get_owner(self, community_id: UUID | str) -> dict[str, Any]: ...
	async def list_member_ids(self, community_id: UUID | str) -> dict[str, Any]: ...


class NotificationService:
	def __init__(
		self,
		repo: NotificationRepositoryProtocol,
		ws_manager: WebSocketManagerProtocol,
		email_client: EmailClientProtocol,
		sms_client: SMSClientProtocol,
		users_client: UsersClientProtocol,
		communities_client: CommunitiesClientProtocol,
		*,
		register_event_listeners: bool = True,
	) -> None:
		self._repo = repo
		self._ws_manager = ws_manager
		self._email_client = email_client
		self._sms_client = sms_client
		self._users_client = users_client
		self._communities_client = communities_client
		self._event_handlers: list[tuple[type[Any], Any]] = []
		if register_event_listeners:
			self._setup_event_listeners()

	def _setup_event_listeners(self) -> None:
		if self._event_handlers:
			return

		async def _friend_request_sent(event: FriendRequestSentEvent) -> None:
			await self._on_friend_request_sent(event)

		async def _friendship_formed(event: FriendshipFormedEvent) -> None:
			await self._on_friendship_formed(event)

		async def _member_joined(event: MemberJoinedEvent) -> None:
			await self._on_member_joined(event)

		async def _post_created(event: PostCreatedEvent) -> None:
			await self._on_post_created(event)

		self._subscribe(FriendRequestSentEvent, _friend_request_sent)
		self._subscribe(FriendshipFormedEvent, _friendship_formed)
		self._subscribe(MemberJoinedEvent, _member_joined)
		self._subscribe(PostCreatedEvent, _post_created)

	def _subscribe(self, event_type: type[Any], handler: Any) -> None:
		bus.subscribe(event_type)(handler)
		self._event_handlers.append((event_type, handler))

	def unsubscribe_event_listeners(self) -> None:
		for event_type, handler in self._event_handlers:
			bus.unsubscribe(event_type, handler)
		self._event_handlers.clear()

	async def get_notifications(self, user_id: UUID | str, limit: int, offset: int) -> dict[str, Any]:
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		normalized_limit = self._normalize_limit(limit)
		normalized_offset = self._normalize_offset(offset)
		notifications = await self._repo.get_for_user(normalized_user_id, normalized_limit, normalized_offset)
		return {"notifications": [self._notification_to_payload(notification) for notification in notifications]}

	async def create_notification(
		self,
		recipient_id: UUID | str,
		type: str,
		payload: dict[str, Any],
	) -> dict[str, Any]:
		notification = await self._repo.create(
			self._parse_uuid(recipient_id, label="recipient id"),
			self._normalize_type(type),
			self._normalize_payload(payload),
		)
		return self._notification_to_payload(notification)

	async def mark_read(self, notification_id: UUID | str, user_id: UUID | str) -> dict[str, Any]:
		normalized_notification_id = self._parse_uuid(notification_id, label="notification id")
		normalized_user_id = self._parse_uuid(user_id, label="user id")
		notification = await self._repo.mark_read(normalized_notification_id, normalized_user_id)
		if notification is None:
			raise NotFoundError("Notification not found")
		return self._notification_to_payload(notification)

	async def mark_all_read(self, user_id: UUID | str) -> None:
		await self._repo.mark_all_read(self._parse_uuid(user_id, label="user id"))

	async def _on_friend_request_sent(self, event: FriendRequestSentEvent) -> None:
		recipient_id = self._parse_uuid(event.receiver_id, label="receiver id")
		payload = {
			"event_id": str(event.event_id),
			"requester_id": str(self._parse_uuid(event.requester_id, label="requester id")),
			"receiver_id": str(recipient_id),
		}
		await self._persist_and_deliver(
			recipient_id=recipient_id,
			notification_type="friend_request_sent",
			payload=payload,
			email=False,
			sms=False,
		)

	async def _on_friendship_formed(self, event: FriendshipFormedEvent) -> None:
		user_ids = [
			self._parse_uuid(event.user_low, label="user low id"),
			self._parse_uuid(event.user_high, label="user high id"),
		]
		for recipient_id in user_ids:
			other_user_id = user_ids[1] if recipient_id == user_ids[0] else user_ids[0]
			payload = {
				"event_id": str(event.event_id),
				"user_id": str(recipient_id),
				"friend_id": str(other_user_id),
			}
			await self._persist_and_deliver(
				recipient_id=recipient_id,
				notification_type="friendship_formed",
				payload=payload,
				email=False,
				sms=False,
			)

	async def _on_member_joined(self, event: MemberJoinedEvent) -> None:
		community_id = self._parse_uuid(event.community_id, label="community id")
		joined_user_id = self._parse_uuid(event.user_id, label="user id")
		owner = await self._communities_client.get_owner(community_id)
		owner_id = self._parse_uuid(owner["owner_id"], label="owner id")
		if owner_id == joined_user_id:
			return

		payload = {
			"event_id": str(event.event_id),
			"community_id": str(community_id),
			"user_id": str(joined_user_id),
			"owner_id": str(owner_id),
		}
		await self._persist_and_deliver(
			recipient_id=owner_id,
			notification_type="member_joined",
			payload=payload,
			email=True,
			sms=False,
		)

	async def _on_post_created(self, event: PostCreatedEvent) -> None:
		community_id = self._parse_uuid(event.community_id, label="community id")
		author_id = self._parse_uuid(event.author_id, label="author id")
		post_id = self._parse_uuid(event.post_id, label="post id")
		members = await self._communities_client.list_member_ids(community_id)

		for member_id_value in members["member_ids"]:
			recipient_id = self._parse_uuid(member_id_value, label="member id")
			if recipient_id == author_id:
				continue

			payload = {
				"event_id": str(event.event_id),
				"post_id": str(post_id),
				"author_id": str(author_id),
				"community_id": str(community_id),
			}
			await self._persist_and_deliver(
				recipient_id=recipient_id,
				notification_type="post_created",
				payload=payload,
				email=True,
				sms=False,
			)

	async def _persist_and_deliver(
		self,
		*,
		recipient_id: UUID,
		notification_type: str,
		payload: dict[str, Any],
		email: bool,
		sms: bool,
	) -> dict[str, Any]:
		try:
			notification = await self._repo.create(recipient_id, notification_type, payload)
			notification_payload = self._notification_to_payload(notification)
			await self._repo.commit()
		except Exception:
			await self._repo.rollback()
			raise

		await self._ws_manager.send_to_user(str(recipient_id), notification_payload)
		if email or sms:
			await self._deliver_out_of_band(recipient_id, notification_type, payload, email=email, sms=sms)
		return notification_payload

	async def _deliver_out_of_band(
		self,
		recipient_id: UUID,
		notification_type: str,
		payload: dict[str, Any],
		*,
		email: bool,
		sms: bool,
	) -> None:
		contact = await self._users_client.get_contact(recipient_id)
		subject = self._notification_subject(notification_type)
		body = self._notification_body(notification_type, payload)
		if email:
			await self._email_client.send_email(
				to_email=contact.get("email"),
				subject=subject,
				body=body,
			)
		if sms:
			await self._sms_client.send_sms(to_phone=contact.get("phone_number"), body=body)

	def _notification_to_payload(self, notification: Any) -> dict[str, Any]:
		return {
			"id": notification.id,
			"recipient_id": notification.recipient_id,
			"type": notification.type,
			"payload": notification.payload,
			"is_read": notification.is_read,
			"created_at": notification.created_at,
		}

	def _notification_subject(self, notification_type: str) -> str:
		subjects = {
			"member_joined": "New community member",
			"post_created": "New community post",
		}
		return subjects.get(notification_type, "New notification")

	def _notification_body(self, notification_type: str, payload: dict[str, Any]) -> str:
		if notification_type == "member_joined":
			return f"User {payload['user_id']} joined community {payload['community_id']}."
		if notification_type == "post_created":
			return f"New post {payload['post_id']} was created in community {payload['community_id']}."
		return "You have a new notification."

	def _parse_uuid(self, value: UUID | str, *, label: str) -> UUID:
		if isinstance(value, UUID):
			return value
		try:
			return UUID(value)
		except (TypeError, ValueError) as exc:
			raise ValidationError(f"Invalid {label}") from exc

	def _normalize_type(self, value: str) -> str:
		if not isinstance(value, str):
			raise ValidationError("Notification type must be a string")
		normalized_value = value.strip()
		if not normalized_value:
			raise ValidationError("Notification type must not be empty")
		if len(normalized_value) > 100:
			raise ValidationError("Notification type must be at most 100 characters")
		return normalized_value

	def _normalize_payload(self, value: dict[str, Any]) -> dict[str, Any]:
		if not isinstance(value, dict):
			raise ValidationError("Notification payload must be an object")
		return value

	def _normalize_limit(self, value: int) -> int:
		if value < 1 or value > 100:
			raise ValidationError("Limit must be between 1 and 100")
		return value

	def _normalize_offset(self, value: int) -> int:
		if value < 0:
			raise ValidationError("Offset must be greater than or equal to 0")
		return value


__all__ = ["NotificationService"]
