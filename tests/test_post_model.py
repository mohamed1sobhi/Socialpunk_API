from __future__ import annotations

from dataclasses import fields

from app.modules.content.models.models import Post
from app.shared.events.events import PostCreatedEvent


def test_post_model_is_always_community_scoped() -> None:
	assert Post.__table__.c.community_id.nullable is False
	assert "visibility" not in Post.__table__.c


def test_post_created_event_has_no_visibility() -> None:
	field_names = {field.name for field in fields(PostCreatedEvent)}

	assert "community_id" in field_names
	assert "visibility" not in field_names
