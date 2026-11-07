from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import ContentBase


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class Post(ContentBase):
	__tablename__ = "posts"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	author_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
	community_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
	title: Mapped[str | None] = mapped_column(String(200), nullable=True)
	body: Mapped[str] = mapped_column(Text, nullable=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=_utcnow,
		onupdate=_utcnow,
	)
	is_deleted: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)

	__table_args__ = (
		Index("ix_posts_community_cursor", "community_id", created_at.desc(), id.desc(),
			postgresql_where=text("is_deleted IS false")),
		Index("ix_posts_author_cursor", "author_id", created_at.desc(), id.desc(),
			postgresql_where=text("is_deleted IS false")),
		Index("ix_posts_feed_cursor", created_at.desc(), id.desc(),
			postgresql_where=text("is_deleted IS false")),
	)


__all__ = ["Post"]
