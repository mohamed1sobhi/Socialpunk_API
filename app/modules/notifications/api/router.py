from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials

from app.modules.notifications.schemas.api_schemas import (
	NotificationListResponse,
	NotificationReadAllResponse,
	NotificationResponse,
)
from app.shared.auth.dependencies import get_current_user, require_permission
from app.shared.exceptions.handlers import UnauthorizedError
from app.shared.dependencies.notifications_deps import (
	get_notification_connection_manager,
	get_notification_service,
)


router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=NotificationListResponse)
async def get_notifications(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_notification_service)],
	limit: Annotated[int, Query(ge=1, le=100)] = 50,
	offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
	notifications = await service.get_notifications(current_user["sub"], limit, offset)
	return NotificationListResponse.model_validate(notifications)


@router.patch("/notifications/read-all", response_model=NotificationReadAllResponse)
async def mark_all_notifications_read(
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_notification_service)],
) -> NotificationReadAllResponse:
	await service.mark_all_read(current_user["sub"])
	return NotificationReadAllResponse(detail="All notifications marked as read")


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
	notification_id: UUID,
	current_user: Annotated[dict[str, Any], Depends(require_permission(audience="user"))],
	service: Annotated[Any, Depends(get_notification_service)],
) -> NotificationResponse:
	notification = await service.mark_read(notification_id, current_user["sub"])
	return NotificationResponse.model_validate(notification)


@router.websocket("/ws/notifications")
async def notifications_websocket(
	websocket: WebSocket,
	token: str,
	manager: Annotated[Any, Depends(get_notification_connection_manager)],
) -> None:
	try:
		credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
		current_user = await require_permission(audience="user")(await get_current_user(credentials))
	except UnauthorizedError:
		await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
		return

	user_id = current_user["sub"]
	await websocket.accept()
	await manager.connect(user_id, websocket)
	try:
		while True:
			await websocket.receive_text()
	except WebSocketDisconnect:
		pass
	finally:
		await manager.disconnect(user_id)


__all__ = ["router"]
