"""Make every post community scoped.

Disposable databases containing unscoped posts must be reset before upgrade.

Revision ID: 4f31c98d27ab
Revises: 807c9b761246
Create Date: 2026-07-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "4f31c98d27ab"
down_revision: str | Sequence[str] | None = "807c9b761246"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "posts",
        "community_id",
        existing_type=sa.Uuid(),
        nullable=False,
        schema="content",
    )
    op.drop_index("ix_content_posts_visibility", table_name="posts", schema="content")
    op.drop_column("posts", "visibility", schema="content")


def downgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "visibility",
            sa.Enum("PUBLIC", "PRIVATE", "COMMUNITY", name="post_visibility", native_enum=False),
            server_default="COMMUNITY",
            nullable=False,
        ),
        schema="content",
    )
    op.create_index(
        "ix_content_posts_visibility",
        "posts",
        ["visibility"],
        unique=False,
        schema="content",
    )
    op.alter_column(
        "posts",
        "visibility",
        existing_type=sa.Enum("PUBLIC", "PRIVATE", "COMMUNITY", name="post_visibility", native_enum=False),
        server_default=None,
        schema="content",
    )
    op.alter_column(
        "posts",
        "community_id",
        existing_type=sa.Uuid(),
        nullable=True,
        schema="content",
    )
