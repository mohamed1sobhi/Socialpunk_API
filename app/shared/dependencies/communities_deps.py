from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.communities.clients.users_client import UsersClient
from app.modules.communities.public.facade import CommunityFacade
from app.modules.communities.repositories.repository import CommunityRepository
from app.modules.communities.services.service import CommunityService
from app.shared.database.session import get_db
from app.shared.config.settings import settings
from app.shared.pagination import CursorPaginator
from app.shared.dependencies.users_deps import get_user_facade


def get_community_repository(
	db: Annotated[AsyncSession, Depends(get_db)],
) -> CommunityRepository:
	return CommunityRepository(db)


def get_community_users_client(
	users_facade=Depends(get_user_facade),
) -> UsersClient:
	return UsersClient(users_facade)


def get_community_pagination() -> CursorPaginator:
	return CursorPaginator(settings.SECRET_KEY)


def get_community_service(
	repo: Annotated[CommunityRepository, Depends(get_community_repository)],
	users_client: Annotated[UsersClient, Depends(get_community_users_client)],
	pagination: Annotated[CursorPaginator, Depends(get_community_pagination)],
) -> CommunityService:
	return CommunityService(repo, users_client, pagination)


def get_community_facade(
	service: Annotated[CommunityService, Depends(get_community_service)],
) -> CommunityFacade:
	return CommunityFacade(service)


__all__ = [
	"get_community_pagination",
	"get_community_facade",
	"get_community_repository",
	"get_community_service",
	"get_community_users_client",
]
