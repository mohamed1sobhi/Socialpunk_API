from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.social_graph.clients.users_client import UsersClient
from app.modules.social_graph.public.facade import SocialGraphFacade
from app.modules.social_graph.repositories.repository import SocialGraphRepository
from app.modules.social_graph.services.service import SocialGraphService
from app.shared.database.session import get_db
from app.shared.config.settings import settings
from app.shared.pagination import CursorPaginator
from app.shared.dependencies.users_deps import get_user_facade


def get_social_graph_repository(
	db: Annotated[AsyncSession, Depends(get_db)],
) -> SocialGraphRepository:
	return SocialGraphRepository(db)


def get_social_graph_users_client(
	users_facade=Depends(get_user_facade),
) -> UsersClient:
	return UsersClient(users_facade)


def get_social_graph_pagination() -> CursorPaginator:
	return CursorPaginator(settings.SECRET_KEY)


def get_social_graph_service(
	repo: Annotated[SocialGraphRepository, Depends(get_social_graph_repository)],
	users_client: Annotated[UsersClient, Depends(get_social_graph_users_client)],
	pagination: Annotated[CursorPaginator, Depends(get_social_graph_pagination)],
) -> SocialGraphService:
	return SocialGraphService(repo, users_client, pagination)


def get_social_graph_facade(
	service: Annotated[SocialGraphService, Depends(get_social_graph_service)],
) -> SocialGraphFacade:
	return SocialGraphFacade(service)


__all__ = [
	"get_social_graph_pagination",
	"get_social_graph_facade",
	"get_social_graph_repository",
	"get_social_graph_service",
	"get_social_graph_users_client",
]
