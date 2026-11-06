from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
from urllib.parse import urlencode
from uuid import UUID, uuid4

import pytest

from app.main import app
from app.shared.auth.jwt import create_access_token
from app.shared.dependencies.admins_deps import get_admin_service
from app.shared.dependencies.communities_deps import get_community_service
from app.shared.dependencies.content_deps import get_content_service
from app.shared.dependencies.notifications_deps import get_notification_service
from app.shared.dependencies.social_graph_deps import get_social_graph_service
from app.shared.exceptions.handlers import ValidationError
from app.shared.pagination import CursorPaginator


def test_cursor_preserves_precision_and_does_not_require_anchor_row() -> None:
	paginator = CursorPaginator("test")
	stamp = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone(timedelta(hours=2)))
	rows = [{"id": UUID(int=i), "created_at": stamp} for i in range(3, 0, -1)]
	items, info = paginator.page(rows, 2, "feed:user-a")
	assert items == rows[:2]
	assert paginator.decode(info["next_cursor"], "feed:user-a") == (stamp.astimezone(timezone.utc), UUID(int=2))
	assert paginator.page([], 2, "feed:user-a")[1] == {"has_more": False, "next_cursor": None}
	assert paginator.page(rows[:2], 2, "feed:user-a")[1]["has_more"] is False


def test_cursor_rejects_tampering_cross_scope_and_key_rotation() -> None:
	paginator = CursorPaginator("test")
	_, info = paginator.page([{"friend_id": UUID(int=i)} for i in range(1, 4)], 2, "friends:user-a", time_field=None, id_field="friend_id")
	token = info["next_cursor"]
	assert paginator.decode(token, "friends:user-a", timestamp=False) == UUID(int=2)
	for invalid in ("", "not-a-cursor", token + "extra", token.replace(".", "x.", 1)):
		with pytest.raises(ValidationError):
			paginator.decode(invalid, "friends:user-a", timestamp=False)
	with pytest.raises(ValidationError):
		paginator.decode(token, "friends:user-b", timestamp=False)
	with pytest.raises(ValidationError):
		paginator.decode(token, "friends:user-a")
	with pytest.raises(ValidationError):
		CursorPaginator("rotated").decode(token, "friends:user-a", timestamp=False)


@pytest.mark.parametrize("limit", [0, -1, 101, True, 1.5, "2"])
def test_invalid_page_sizes_are_rejected(limit: Any) -> None:
	with pytest.raises(ValidationError):
		CursorPaginator("test").limit(limit)


class EmptyListServices:
	page_info = {"has_more": False, "next_cursor": None}

	async def list_feed(self, viewer: Any, **page: Any) -> dict[str, Any]:
		return {"posts": [], "page_info": self.page_info}

	async def list_user_posts(self, author: Any, viewer: Any, **page: Any) -> dict[str, Any]:
		return {"author_id": author, "posts": [], "page_info": self.page_info}

	async def list_community_posts(self, community: Any, viewer: Any, **page: Any) -> dict[str, Any]:
		return {"community_id": community, "posts": [], "page_info": self.page_info}

	async def list_public_communities(self, **page: Any) -> dict[str, Any]:
		return {"communities": [], "page_info": self.page_info}

	async def list_members(self, viewer: Any, community: Any, **page: Any) -> dict[str, Any]:
		return {"community_id": community, "members": [], "page_info": self.page_info}

	async def get_friends(self, user: Any, **page: Any) -> dict[str, Any]:
		return {"user_id": user, "friend_ids": [], "page_info": self.page_info}

	async def get_pending_requests(self, user: Any, **page: Any) -> dict[str, Any]:
		return {"user_id": user, "requests": [], "page_info": self.page_info}

	async def get_notifications(self, user: Any, limit: int, after: str | None) -> dict[str, Any]:
		return {"notifications": [], "page_info": self.page_info}

	async def list_roles(self, *, limit: int, offset: int) -> dict[str, Any]:
		return {"roles": [], "page_info": {"limit": limit, "offset": offset, "has_more": False, "next_offset": None}}


async def request(path: str, query: dict[str, Any], *, system: bool = False) -> tuple[int, dict[str, Any]]:
	status = 0
	body = bytearray()
	token = create_access_token(uuid4(), audience="system" if system else "user", permissions=["admins.roles.manage"] if system else [])

	async def receive() -> dict[str, Any]:
		return {"type": "http.request", "body": b"", "more_body": False}

	async def send(message: Any) -> None:
		nonlocal status
		if message["type"] == "http.response.start":
			status = message["status"]
		elif message["type"] == "http.response.body":
			body.extend(message.get("body", b""))

	await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "scheme": "http",
		"method": "GET", "path": path, "raw_path": path.encode(), "query_string": urlencode(query).encode(),
		"headers": [(b"authorization", f"Bearer {token}".encode())], "server": ("testserver", 80), "client": ("testclient", 12345)}, receive, send)
	return status, json.loads(body)


@pytest.fixture
def empty_services():
	providers = (get_content_service, get_community_service, get_social_graph_service, get_notification_service, get_admin_service)
	service = EmptyListServices()
	for provider in providers:
		app.dependency_overrides[provider] = lambda: service
	try:
		yield
	finally:
		for provider in providers:
			app.dependency_overrides.pop(provider, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
	"/api/v1/posts", f"/api/v1/users/{uuid4()}/posts", f"/api/v1/communities/{uuid4()}/posts",
	"/api/v1/notifications", "/api/v1/communities", f"/api/v1/communities/{uuid4()}/members",
	"/api/v1/social/friends", "/api/v1/social/friends/requests/pending",
])
async def test_cursor_http_contract_and_removed_offsets(empty_services: Any, path: str) -> None:
	status, payload = await request(path, {"limit": 2})
	assert status == 200
	assert payload["page_info"] == {"next_cursor": None, "has_more": False}
	for query in ({"limit": 0}, {"limit": 101}, {"after": ""}, {"after": "x" * 2049}, {"offset": 1}):
		assert (await request(path, query))[0] == 422


@pytest.mark.asyncio
async def test_admin_offset_http_contract(empty_services: Any) -> None:
	status, payload = await request("/api/v1/admins/roles", {"limit": 2, "offset": 4}, system=True)
	assert status == 200
	assert payload["page_info"] == {"limit": 2, "offset": 4, "next_offset": None, "has_more": False}
	for query in ({"offset": -1}, {"limit": 101}, {"offset": "invalid"}, {"after": "cursor"}):
		assert (await request("/api/v1/admins/roles", query, system=True))[0] == 422
