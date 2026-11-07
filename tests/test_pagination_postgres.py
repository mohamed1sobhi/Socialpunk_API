from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError

from app.modules.admins.models.models import Role
from app.modules.admins.repositories.repository import AdminRepository
from app.modules.admins.services.service import AdminService
from app.modules.communities.models.models import Community, CommunityMember, CommunityRole, CommunityVisibility
from app.modules.communities.public.facade import CommunityFacade
from app.modules.communities.repositories.repository import CommunityRepository
from app.modules.communities.services.service import CommunityService
from app.modules.content.clients.communities_client import CommunitiesClient as ContentCommunitiesClient
from app.modules.content.models.models import Post
from app.modules.content.repositories.repository import ContentRepository
from app.modules.content.services.service import ContentService
from app.modules.notifications.clients.communities_client import CommunitiesClient as NotificationCommunitiesClient
from app.modules.notifications.models.models import Notification
from app.modules.notifications.repositories.repository import NotificationRepository
from app.modules.notifications.services.service import NotificationService
from app.modules.social_graph.models.models import FriendRequest, FriendRequestStatus, Friendship
from app.modules.social_graph.repositories.repository import SocialGraphRepository
from app.modules.social_graph.services.service import SocialGraphService
from app.shared.events.events import PostCreatedEvent
from app.shared.exceptions.handlers import ForbiddenError, ValidationError
from app.shared.pagination import CursorPaginator


NOW = datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)


class ActiveUsers:
	async def get_user(self, user_id: Any) -> dict[str, Any]:
		return {"id": user_id, "is_active": True}


class NoDelivery:
	async def send_to_user(self, user_id: UUID, payload: dict[str, Any]) -> bool:
		return True

	async def send_email(self, *, to_email: str | None, subject: str, body: str) -> bool:
		return True

	async def send_sms(self, *, to_phone: str | None, body: str) -> bool:
		return True

	async def get_contact(self, user_id: UUID | str) -> dict[str, Any]:
		return {}


def community_service(session: Any) -> CommunityService:
	return CommunityService(CommunityRepository(session), ActiveUsers(), CursorPaginator("test"))


async def add_community(session: Any, *, private: bool = False) -> Community:
	row = Community(id=uuid4(), name="Test", owner_id=uuid4(), created_at=NOW,
		visibility=CommunityVisibility.PRIVATE if private else CommunityVisibility.PUBLIC)
	session.add(row)
	await session.flush()
	return row


async def add_members(session: Any, community: Community, count: int) -> list[UUID]:
	role = CommunityRole(id=uuid4(), name=f"member-{uuid4()}")
	session.add(role)
	await session.flush()
	user_ids = [uuid4() for _ in range(count)]
	await session.execute(insert(CommunityMember), [{"id": UUID(int=i + 1), "user_id": user,
		"community_id": community.id, "role_id": role.id, "joined_at": NOW} for i, user in enumerate(user_ids)])
	return user_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["feed", "author", "community"])
async def test_post_keysets_survive_ties_anchor_deletion_and_new_inserts(pg_session: Any, surface: str) -> None:
	community = await add_community(pg_session)
	private = await add_community(pg_session, private=True)
	author = uuid4()
	pg_session.add_all([Post(id=UUID(int=i), author_id=author, community_id=community.id,
		body="body", created_at=NOW, is_deleted=(i == 3)) for i in range(1, 8)])
	pg_session.add(Post(id=UUID(int=100), author_id=author, community_id=private.id, body="hidden", created_at=NOW))
	await pg_session.flush()
	service = ContentService(ContentRepository(pg_session), ContentCommunitiesClient(CommunityFacade(community_service(pg_session))), CursorPaginator("test"))

	async def page(after: str | None = None) -> dict[str, Any]:
		if surface == "feed":
			return await service.list_feed(None, limit=2, after=after)
		if surface == "author":
			return await service.list_user_posts(author, None, limit=2, after=after)
		return await service.list_community_posts(community.id, None, limit=2, after=after)

	first = await page()
	assert [post["id"].int for post in first["posts"]] == [7, 6]
	assert first["page_info"]["has_more"]
	await pg_session.execute(delete(Post).where(Post.id == UUID(int=6)))
	pg_session.add(Post(id=uuid4(), author_id=author, community_id=community.id, body="new", created_at=NOW + timedelta(seconds=1)))
	await pg_session.flush()
	seen = [7, 6]
	current = first
	while current["page_info"]["has_more"]:
		current = await page(current["page_info"]["next_cursor"])
		assert len(current["posts"]) <= 2
		seen.extend(post["id"].int for post in current["posts"])
	assert seen == [7, 6, 5, 4, 2, 1]
	assert current["page_info"]["next_cursor"] is None


@pytest.mark.asyncio
async def test_content_rechecks_membership_and_rejects_cross_viewer_cursor(pg_session: Any) -> None:
	public = await add_community(pg_session)
	private = await add_community(pg_session, private=True)
	viewer = (await add_members(pg_session, private, 1))[0]
	pg_session.add_all([Post(id=UUID(int=i), author_id=uuid4(), community_id=private.id if i > 3 else public.id,
		body="body", created_at=NOW) for i in range(1, 7)])
	await pg_session.flush()
	service = ContentService(ContentRepository(pg_session), ContentCommunitiesClient(CommunityFacade(community_service(pg_session))), CursorPaginator("test"))
	first = await service.list_feed(viewer, limit=2)
	private_first = await service.list_community_posts(private.id, viewer, limit=2)
	assert [row["id"].int for row in first["posts"]] == [6, 5]
	with pytest.raises(ValidationError):
		await service.list_feed(None, after=first["page_info"]["next_cursor"])
	with pytest.raises(ValidationError):
		await service.list_user_posts(uuid4(), viewer, after=first["page_info"]["next_cursor"])
	await pg_session.execute(delete(CommunityMember).where(CommunityMember.user_id == viewer))
	second = await service.list_feed(viewer, limit=2, after=first["page_info"]["next_cursor"])
	assert [row["id"].int for row in second["posts"]] == [3, 2]
	with pytest.raises(ForbiddenError):
		await service.list_community_posts(private.id, viewer, after=private_first["page_info"]["next_cursor"])


@pytest.mark.asyncio
async def test_notification_cursor_is_recipient_scoped_and_read_state_independent(pg_session: Any) -> None:
	user, other = uuid4(), uuid4()
	pg_session.add_all([Notification(id=UUID(int=i), recipient_id=user, type="test", created_at=NOW) for i in range(1, 6)])
	pg_session.add(Notification(id=UUID(int=100), recipient_id=other, type="hidden", created_at=NOW))
	await pg_session.flush()
	infra = NoDelivery()
	service = NotificationService(NotificationRepository(pg_session), infra, infra, infra, infra,
		NotificationCommunitiesClient(CommunityFacade(community_service(pg_session))), CursorPaginator("test"), register_event_listeners=False)
	first = await service.get_notifications(user, limit=2)
	assert [row["id"].int for row in first["notifications"]] == [5, 4]
	await service.mark_all_read(user)
	await pg_session.execute(delete(Notification).where(Notification.id == UUID(int=4)))
	pg_session.add(Notification(id=uuid4(), recipient_id=user, type="new", created_at=NOW + timedelta(seconds=1)))
	await pg_session.flush()
	second = await service.get_notifications(user, limit=2, after=first["page_info"]["next_cursor"])
	assert [row["id"].int for row in second["notifications"]] == [3, 2]
	assert all(row["is_read"] for row in second["notifications"])
	with pytest.raises(ValidationError):
		await service.get_notifications(other, after=first["page_info"]["next_cursor"])
	last = await service.get_notifications(user, limit=2, after=second["page_info"]["next_cursor"])
	assert [row["id"].int for row in last["notifications"]] == [1]
	assert not last["page_info"]["has_more"]


@pytest.mark.asyncio
async def test_public_discovery_members_and_internal_batches_use_stable_order(pg_session: Any) -> None:
	communities = [await add_community(pg_session, private=(i == 2)) for i in range(5)]
	service = community_service(pg_session)
	current = await service.list_public_communities(limit=2)
	seen = list(current["communities"])
	while current["page_info"]["has_more"]:
		current = await service.list_public_communities(limit=2, after=current["page_info"]["next_cursor"])
		seen.extend(current["communities"])
	assert [row["id"] for row in seen] == sorted([row.id for i, row in enumerate(communities) if i != 2], reverse=True)
	community = communities[0]
	users = await add_members(pg_session, community, 5)
	first = await service.list_members(users[0], community.id, limit=2)
	assert [row["id"].int for row in first["members"]] == [1, 2]
	await pg_session.execute(delete(CommunityMember).where(CommunityMember.id == UUID(int=2)))
	second = await service.list_members(users[0], community.id, limit=2, after=first["page_info"]["next_cursor"])
	assert [row["id"].int for row in second["members"]] == [3, 4]
	client = NotificationCommunitiesClient(CommunityFacade(service))
	batch = await client.list_member_ids(community.id, limit=2)
	ids = list(batch["member_ids"])
	while batch["page_info"]["has_more"]:
		batch = await client.list_member_ids(community.id, limit=2, after=batch["page_info"]["next_cursor"])
		ids.extend(batch["member_ids"])
	assert ids == [users[0], *users[2:]]
	with pytest.raises(ValidationError):
		await service.list_members(users[1], community.id, after=first["page_info"]["next_cursor"])
	with pytest.raises(ValidationError):
		await service.list_member_ids(community.id, after=first["page_info"]["next_cursor"])
	joined = await service.list_user_communities(users[0], limit=2)
	assert [row["id"] for row in joined["communities"]] == [community.id]


@pytest.mark.asyncio
async def test_pending_pair_uniqueness_and_pending_pagination(pg_session: Any) -> None:
	repo = SocialGraphRepository(pg_session)
	user, requester = uuid4(), uuid4()
	first = await repo.create_request(request_id=uuid4(), requester_id=requester, receiver_id=user)
	assert await repo.get_pending_request_for_pair(user, requester) == first
	for a, b in ((requester, user), (user, requester)):
		with pytest.raises(IntegrityError):
			async with pg_session.begin_nested():
				await repo.create_request(request_id=uuid4(), requester_id=a, receiver_id=b)
	pg_session.add(FriendRequest(id=uuid4(), requester_id=user, receiver_id=requester, status=FriendRequestStatus.REJECTED))
	await pg_session.flush()
	service = SocialGraphService(repo, ActiveUsers(), CursorPaginator("test"))
	friendship = await service.respond_to_request(user, first["id"], accept=True)
	assert friendship["user_low"] < friendship["user_high"]
	assert await repo.get_request_by_id(first["id"]) is None
	pg_session.add_all([FriendRequest(id=UUID(int=i), requester_id=uuid4(), receiver_id=user,
		status=FriendRequestStatus.REJECTED if i == 3 else FriendRequestStatus.PENDING, created_at=NOW) for i in range(1, 7)])
	await pg_session.flush()
	page = await service.get_pending_requests(user, limit=2)
	seen = [row["id"].int for row in page["requests"]]
	while page["page_info"]["has_more"]:
		page = await service.get_pending_requests(user, limit=2, after=page["page_info"]["next_cursor"])
		seen.extend(row["id"].int for row in page["requests"])
	assert seen == [6, 5, 4, 2, 1]


@pytest.mark.asyncio
async def test_friends_merge_both_canonical_directions(pg_session: Any) -> None:
	user = UUID(int=50)
	friend_ids = [UUID(int=i) for i in (1, 2, 3, 4, 60, 61, 62, 63)]
	pg_session.add_all([Friendship(user_low=min(user, friend), user_high=max(user, friend), created_at=NOW) for friend in friend_ids])
	await pg_session.flush()
	service = SocialGraphService(SocialGraphRepository(pg_session), ActiveUsers(), CursorPaginator("test"))
	page = await service.get_friends(user, limit=3)
	seen = list(page["friend_ids"])
	while page["page_info"]["has_more"]:
		page = await service.get_friends(user, limit=3, after=page["page_info"]["next_cursor"])
		seen.extend(page["friend_ids"])
	assert seen == friend_ids
	assert len(set(seen)) == 8


@pytest.mark.asyncio
async def test_notification_fanout_exhausts_all_member_batches(pg_session: Any, monkeypatch: Any) -> None:
	community = await add_community(pg_session)
	users = await add_members(pg_session, community, 1002)
	client = NotificationCommunitiesClient(CommunityFacade(community_service(pg_session)))
	infra = NoDelivery()
	service = NotificationService(NotificationRepository(pg_session), infra, infra, infra, infra, client, CursorPaginator("test"), register_event_listeners=False)
	delivered = []
	cursors = []
	original = client.list_member_ids

	async def batch(community_id: Any, *, limit: int, after: str | None) -> dict[str, Any]:
		cursors.append(after)
		return await original(community_id, limit=limit, after=after)

	async def deliver(**payload: Any) -> None:
		delivered.append(payload["recipient_id"])

	monkeypatch.setattr(client, "list_member_ids", batch)
	monkeypatch.setattr(service, "_persist_and_deliver", deliver)
	await service._on_post_created(PostCreatedEvent(community_id=str(community.id), author_id=str(users[0]), post_id=str(uuid4())))
	assert delivered == users[1:]
	assert len(cursors) == 3 and cursors[0] is None
	assert cursors[1] and cursors[2] and cursors[1] != cursors[2]


@pytest.mark.asyncio
async def test_admin_roles_offset_order_and_continuation(pg_session: Any) -> None:
	pg_session.add_all([Role(id=uuid4(), name=name) for name in ("zeta", "alpha", "gamma", "beta", "delta")])
	await pg_session.flush()
	service = AdminService(AdminRepository(pg_session))
	first = await service.list_roles(limit=2)
	assert [role["name"] for role in first["roles"]] == ["alpha", "beta"]
	assert first["page_info"]["next_offset"] == 2
	second = await service.list_roles(limit=2, offset=2)
	assert [role["name"] for role in second["roles"]] == ["delta", "gamma"]
	last = await service.list_roles(limit=2, offset=4)
	assert [role["name"] for role in last["roles"]] == ["zeta"]
	assert last["page_info"]["next_offset"] is None
	assert not last["page_info"]["has_more"]


@pytest.mark.asyncio
async def test_representative_explain_plans_seek_instead_of_skipping(pg_session: Any) -> None:
	from scripts.benchmark_pagination import benchmark, plan_nodes
	schemas = pg_session.bind.sync_connection.get_execution_options()["schema_translate_map"]
	reports = await benchmark(pg_session, schemas, 10000)
	by_case = {(report["query"], report["mode"]): report for report in reports}
	for name in ("community_posts", "feed_broad", "notifications", "members", "pending_requests", "friends"):
		cursor = by_case[name, "cursor_deep"]
		offset = by_case[name, "offset_deep"]
		assert cursor["indexes"], (name, cursor["plan"])
		assert cursor["scan_rows"] < offset["scan_rows"] / 10
		assert cursor["shared_blocks"] < offset["shared_blocks"]
	for name in ("community_posts_sparse", "author_posts_sparse", "notifications_sparse", "pending_requests_sparse"):
		assert by_case[name, "cursor_deep"]["indexes"]
	# Confirm tuple cursors became index conditions, not just residual filters.
	for name in ("notifications", "members", "pending_requests", "public_communities"):
		nodes = plan_nodes(by_case[name, "cursor_deep"]["plan"]["Plan"])
		assert any("ROW(" in node.get("Index Cond", "") for node in nodes)
	assert "uq_friend_requests_pending_pair" in by_case["pending_pair_lookup", "operation"]["indexes"]
	assert "ix_notifications_unread_recipient" in by_case["mark_unread_read_sparse", "operation"]["indexes"]
