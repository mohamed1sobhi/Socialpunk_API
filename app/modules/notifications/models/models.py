from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import NotificationsBase


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class Notification(NotificationsBase):
	__tablename__ = "notifications"

	id: Mapped[UUID] = mapped_column(primary_key=True)
	recipient_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
	type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
	payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
	is_read: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

	__table_args__ = (
		Index("ix_notifications_recipient_cursor", "recipient_id", created_at.desc(), id.desc()),
		Index("ix_notifications_unread_recipient", "recipient_id", postgresql_where=text("is_read IS false")),
	)


__all__ = ["Notification"]
