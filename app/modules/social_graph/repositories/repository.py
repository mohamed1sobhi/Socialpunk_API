from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.social_graph.models.models import FriendRequest, FriendRequestStatus, Friendship


class SocialGraphRepository:
	def __init__(self, session: AsyncSession) -> None:
		self._session = session

	@staticmethod
	def _request_payload(request: FriendRequest) -> dict[str, Any]:
		return {
			**{field: getattr(request, field) for field in (
				"id", "requester_id", "receiver_id", "created_at", "updated_at",
			)},
			"status": request.status.value,
		}

	@staticmethod
	def _friendship_payload(friendship: Friendship) -> dict[str, Any]:
		return {field: getattr(friendship, field) for field in ("user_low", "user_high", "created_at")}

	async def get_friendship(self, user_a: UUID, user_b: UUID) -> dict[str, Any] | None:
		user_low, user_high = self._canonical_pair(user_a, user_b)
		statement = select(Friendship).where(
			Friendship.user_low == user_low,
			Friendship.user_high == user_high,
		)
		friendship = await self._session.scalar(statement)
		return self._friendship_payload(friendship) if friendship is not None else None

	async def _get_request(self, request_id: UUID) -> FriendRequest | None:
		statement = select(FriendRequest).where(FriendRequest.id == request_id)
		return await self._session.scalar(statement)

	async def get_request_by_id(self, request_id: UUID) -> dict[str, Any] | None:
		request = await self._get_request(request_id)
		return self._request_payload(request) if request is not None else None

	async def get_pending_request_for_pair(self, user_a: UUID, user_b: UUID) -> dict[str, Any] | None:
		statement = select(FriendRequest).where(
			FriendRequest.status == FriendRequestStatus.PENDING,
			or_(
				and_(FriendRequest.requester_id == user_a, FriendRequest.receiver_id == user_b),
				and_(FriendRequest.requester_id == user_b, FriendRequest.receiver_id == user_a),
			),
		)
		request = await self._session.scalar(statement)
		return self._request_payload(request) if request is not None else None

	async def create_request(
		self,
		*,
		request_id: UUID,
		requester_id: UUID,
		receiver_id: UUID,
	) -> dict[str, Any]:
		friend_request = FriendRequest(
			id=request_id,
			requester_id=requester_id,
			receiver_id=receiver_id,
			status=FriendRequestStatus.PENDING,
		)
		self._session.add(friend_request)
		await self._session.flush()
		return self._request_payload(friend_request)

	async def reject_request(self, request_id: UUID) -> dict[str, Any] | None:
		friend_request = await self._get_request(request_id)
		if friend_request is None:
			return None

		friend_request.status = FriendRequestStatus.REJECTED
		friend_request.updated_at = datetime.now(timezone.utc)
		await self._session.flush()
		return self._request_payload(friend_request)

	async def create_friendship(self, user_a: UUID, user_b: UUID) -> dict[str, Any]:
		user_low, user_high = self._canonical_pair(user_a, user_b)
		friendship = Friendship(user_low=user_low, user_high=user_high)
		self._session.add(friendship)
		await self._session.flush()
		return self._friendship_payload(friendship)

	async def delete_request(self, request_id: UUID) -> None:
		friend_request = await self._get_request(request_id)
		if friend_request is None:
			return

		await self._session.delete(friend_request)
		await self._session.flush()

	async def get_friends(self, user_id: UUID) -> list[UUID]:
		statement = select(Friendship).where(
			or_(Friendship.user_low == user_id, Friendship.user_high == user_id)
		)
		friendships = (await self._session.scalars(statement)).all()
		return [
			friendship.user_high if friendship.user_low == user_id else friendship.user_low
			for friendship in friendships
		]

	async def get_pending_requests(self, user_id: UUID) -> list[dict[str, Any]]:
		statement = (
			select(FriendRequest)
			.where(
				FriendRequest.receiver_id == user_id,
				FriendRequest.status == FriendRequestStatus.PENDING,
			)
			.order_by(FriendRequest.created_at.desc())
		)
		return [self._request_payload(row) for row in (await self._session.scalars(statement)).all()]

	def _canonical_pair(self, user_a: UUID, user_b: UUID) -> tuple[UUID, UUID]:
		return (user_a, user_b) if user_a.int < user_b.int else (user_b, user_a)


__all__ = ["SocialGraphRepository"]
