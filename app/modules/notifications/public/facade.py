from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.notifications.schemas.public_schemas.requests import (
	CreateNotificationRequest,
	MarkAllNotificationsReadRequest,
	NotificationListRequest,
	NotificationLookupRequest,
)


class NotificationServiceProtocol(Protocol):
	async def create_notification(
		self,
		recipient_id: UUID | str,
		type: str,
		payload: dict[str, Any],
	) -> dict[str, Any]: ...
	async def get_notifications(self, user_id: UUID | str, limit: int, after: str | None) -> dict[str, Any]: ...
	async def mark_read(self, notification_id: UUID | str, user_id: UUID | str) -> dict[str, Any]: ...
	async def mark_all_read(self, user_id: UUID | str) -> None: ...


class NotificationFacade:
	def __init__(self, service: NotificationServiceProtocol) -> None:
		self._service = service

	async def create_notification(
		self,
		recipient_id: UUID | str,
		type: str,
		payload: dict[str, Any],
	) -> dict[str, Any]:
		request = CreateNotificationRequest.model_validate(
			{"recipient_id": recipient_id, "type": type, "payload": payload}
		)
		return await self._service.create_notification(request.recipient_id, request.type, request.payload)

	async def get_notifications(
		self,
		user_id: UUID | str,
		limit: int = 50,
		after: str | None = None,
	) -> dict[str, Any]:
		request = NotificationListRequest.model_validate(
			{"user_id": user_id, "limit": limit, "after": after}
		)
		return await self._service.get_notifications(request.user_id, request.limit, request.after)

	async def mark_read(self, notification_id: UUID | str, user_id: UUID | str) -> dict[str, Any]:
		request = NotificationLookupRequest.model_validate(
			{"notification_id": notification_id, "user_id": user_id}
		)
		return await self._service.mark_read(request.notification_id, request.user_id)

	async def mark_all_read(self, user_id: UUID | str) -> None:
		request = MarkAllNotificationsReadRequest.model_validate({"user_id": user_id})
		await self._service.mark_all_read(request.user_id)


__all__ = ["NotificationFacade"]
