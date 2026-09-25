"""Add the system post-deletion permission flag.

Revision ID: c3a51b8e6294
Revises: b2d4e6f8a901
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c3a51b8e6294"
down_revision: str | Sequence[str] | None = "b2d4e6f8a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("can_delete_posts", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="admins",
    )


def downgrade() -> None:
    op.drop_column("roles", "can_delete_posts", schema="admins")
