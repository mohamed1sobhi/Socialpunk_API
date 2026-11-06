from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.clients.communities_client import CommunitiesClient
from app.modules.notifications.clients.users_client import UsersClient
from app.modules.notifications.public.facade import NotificationFacade
from app.modules.notifications.repositories.repository import NotificationRepository
from app.modules.notifications.services.service import NotificationService
from app.shared.database.session import AsyncSessionLocal, get_db
from app.shared.config.settings import settings
from app.shared.pagination import CursorPaginator
from app.shared.dependencies.communities_deps import (
	get_community_facade,
	get_community_repository,
	get_community_service,
	get_community_users_client,
	get_community_pagination,
)
from app.shared.dependencies.users_deps import get_user_facade, get_user_repository, get_user_service
from app.shared.email_client import EmailClient
from app.shared.sms_client import TwilioSMSClient
from app.shared.websockets.manager import connection_manager


_notification_service_singleton: NotificationService | None = None
_startup_sessions: list[AsyncSession] = []


def get_notification_repository(
	db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRepository:
	return NotificationRepository(db)


def get_notification_users_client(
	users_facade=Depends(get_user_facade),
) -> UsersClient:
	return UsersClient(users_facade)


def get_notification_communities_client(
	communities_facade=Depends(get_community_facade),
) -> CommunitiesClient:
	return CommunitiesClient(communities_facade)


def get_email_client() -> EmailClient:
	return EmailClient()


def get_sms_client() -> TwilioSMSClient:
	return TwilioSMSClient()


def get_notification_connection_manager():
	return connection_manager


def get_notification_pagination() -> CursorPaginator:
	return CursorPaginator(settings.SECRET_KEY)


def get_notification_service(
	repo: Annotated[NotificationRepository, Depends(get_notification_repository)],
	users_client: Annotated[UsersClient, Depends(get_notification_users_client)],
	communities_client: Annotated[CommunitiesClient, Depends(get_notification_communities_client)],
	email_client: Annotated[EmailClient, Depends(get_email_client)],
	sms_client: Annotated[TwilioSMSClient, Depends(get_sms_client)],
	pagination: Annotated[CursorPaginator, Depends(get_notification_pagination)],
) -> NotificationService:
	return NotificationService(
		repo,
		connection_manager,
		email_client,
		sms_client,
		users_client,
		communities_client,
		pagination,
		register_event_listeners=False,
	)


def get_notification_facade(
	service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationFacade:
	return NotificationFacade(service)


async def create_notification_service_singleton() -> NotificationService:
	global _notification_service_singleton, _startup_sessions

	if _notification_service_singleton is not None:
		return _notification_service_singleton

	notifications_db = AsyncSessionLocal()
	users_db = AsyncSessionLocal()
	communities_db = AsyncSessionLocal()
	_startup_sessions = [notifications_db, users_db, communities_db]

	users_repo = get_user_repository(users_db)
	users_service = get_user_service(users_repo)
	users_facade = get_user_facade(users_service)

	community_repo = get_community_repository(communities_db)
	community_users_client = get_community_users_client(users_facade)
	community_service = get_community_service(community_repo, community_users_client, get_community_pagination())
	community_facade = get_community_facade(community_service)

	_notification_service_singleton = NotificationService(
		NotificationRepository(notifications_db),
		connection_manager,
		EmailClient(),
		TwilioSMSClient(),
		UsersClient(users_facade),
		CommunitiesClient(community_facade),
		get_notification_pagination(),
		register_event_listeners=True,
	)
	return _notification_service_singleton


async def close_notification_service_singleton() -> None:
	global _notification_service_singleton, _startup_sessions

	if _notification_service_singleton is not None:
		_notification_service_singleton.unsubscribe_event_listeners()
	for session in _startup_sessions:
		await session.close()
	_startup_sessions = []
	_notification_service_singleton = None


__all__ = [
	"get_notification_pagination",
	"close_notification_service_singleton",
	"create_notification_service_singleton",
	"get_email_client",
	"get_notification_communities_client",
	"get_notification_connection_manager",
	"get_notification_facade",
	"get_notification_repository",
	"get_notification_service",
	"get_notification_users_client",
	"get_sms_client",
]
