"""Correct pending-pair uniqueness and add ordered pagination indexes.

Revision ID: d7e9a102bc34
Revises: c3a51b8e6294
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e9a102bc34"
down_revision = "c3a51b8e6294"
branch_labels = None
depends_on = None


INDEXES = (
	("content", "posts", "ix_posts_community_cursor", ["community_id", sa.text("created_at DESC"), sa.text("id DESC")], "is_deleted IS false"),
	("content", "posts", "ix_posts_author_cursor", ["author_id", sa.text("created_at DESC"), sa.text("id DESC")], "is_deleted IS false"),
	("content", "posts", "ix_posts_feed_cursor", [sa.text("created_at DESC"), sa.text("id DESC")], "is_deleted IS false"),
	("notifications", "notifications", "ix_notifications_recipient_cursor", ["recipient_id", sa.text("created_at DESC"), sa.text("id DESC")], None),
	("notifications", "notifications", "ix_notifications_unread_recipient", ["recipient_id"], "is_read IS false"),
	("communities", "communities", "ix_communities_public_cursor", [sa.text("created_at DESC"), sa.text("id DESC")], "visibility = 'public'"),
	("social_graph", "friend_requests", "ix_friend_requests_receiver_cursor", ["receiver_id", sa.text("created_at DESC"), sa.text("id DESC")], "status = 'PENDING'"),
	("social_graph", "friendships", "ix_friendships_reverse_pair", ["user_high", "user_low"], None),
)


def upgrade() -> None:
	# Fail with an actionable message without silently modifying existing data.
	op.execute("""DO $$ BEGIN
		IF EXISTS (SELECT 1 FROM communities.communities WHERE visibility NOT IN ('public', 'private')) THEN
			RAISE EXCEPTION 'Inspect/normalize visibility with python -m scripts.inspect_pagination_data --normalize-visibility before upgrading';
		END IF;
		IF EXISTS (
			SELECT 1 FROM social_graph.friend_requests WHERE status = 'PENDING'
			GROUP BY least(requester_id, receiver_id), greatest(requester_id, receiver_id)
			HAVING count(*) > 1
		) THEN
			RAISE EXCEPTION 'Resolve duplicate pending pairs reported by python -m scripts.inspect_pagination_data before upgrading';
		END IF;
	END $$""")
	op.drop_index("uq_friend_requests_pending_pair", table_name="friend_requests", schema="social_graph")
	op.create_index("uq_friend_requests_pending_pair", "friend_requests",
		[sa.text("least(requester_id, receiver_id)"), sa.text("greatest(requester_id, receiver_id)")],
		unique=True, schema="social_graph", postgresql_where=sa.text("status = 'PENDING'"))
	for schema, table, name, columns, predicate in INDEXES:
		if predicate:
			op.create_index(name, table, columns, schema=schema, postgresql_where=sa.text(predicate))
		else:
			op.create_index(name, table, columns, schema=schema)
	op.create_index("ix_community_members_cursor", "community_members", ["community_id", "joined_at", "id"],
		schema="communities", postgresql_include=["user_id"])


def downgrade() -> None:
	op.drop_index("ix_community_members_cursor", table_name="community_members", schema="communities")
	for schema, table, name, _, _ in reversed(INDEXES):
		op.drop_index(name, table_name=table, schema=schema)
	op.drop_index("uq_friend_requests_pending_pair", table_name="friend_requests", schema="social_graph")
	op.create_index("uq_friend_requests_pending_pair", "friend_requests",
		[sa.text("least(requester_id, receiver_id)"), sa.text("greatest(requester_id, receiver_id)")],
		unique=True, schema="social_graph", postgresql_where=sa.text("status = 'pending'"))
