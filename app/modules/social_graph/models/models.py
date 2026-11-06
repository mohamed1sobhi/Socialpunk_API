from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import SocialGraphBase


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class FriendRequestStatus(str, Enum):
	PENDING = "pending"
	REJECTED = "rejected"


class FriendRequest(SocialGraphBase):
	__tablename__ = "friend_requests"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	requester_id: Mapped[UUID] = mapped_column(nullable=False)
	receiver_id: Mapped[UUID] = mapped_column(nullable=False)
	status: Mapped[FriendRequestStatus] = mapped_column(
		SqlEnum(FriendRequestStatus, name="friend_request_status", native_enum=False),
		nullable=False,
		default=FriendRequestStatus.PENDING,
	)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=_utcnow,
		onupdate=_utcnow,
	)

	__table_args__ = (
		CheckConstraint("requester_id <> receiver_id", name="ck_friend_requests_distinct_users"),
		Index(
			"uq_friend_requests_pending_pair",
			func.least(requester_id, receiver_id),
			func.greatest(requester_id, receiver_id),
			unique=True,
			postgresql_where=text("status = 'PENDING'"),
		),
		Index("ix_friend_requests_receiver_cursor", "receiver_id", created_at.desc(), id.desc(),
			postgresql_where=text("status = 'PENDING'")),
	)


class Friendship(SocialGraphBase):
	__tablename__ = "friendships"

	user_low: Mapped[UUID] = mapped_column(primary_key=True)
	user_high: Mapped[UUID] = mapped_column(primary_key=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

	__table_args__ = (
		CheckConstraint("user_low < user_high", name="ck_friendships_canonical_pair"),
		Index("ix_friendships_user_low", "user_low"),
		Index("ix_friendships_user_high", "user_high"),
		Index("ix_friendships_reverse_pair", "user_high", "user_low"),
	)


__all__ = ["FriendRequest", "FriendRequestStatus", "Friendship"]
