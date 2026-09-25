"""Replace permission catalogs and join tables with fixed role flags.

Revision ID: b2d4e6f8a901
Revises: 4f31c98d27ab
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4e6f8a901"
down_revision: str | Sequence[str] | None = "4f31c98d27ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	for column_name in (
		"can_manage_system_users",
		"can_read_system_users",
		"can_manage_roles",
		"can_read_system_permissions",
	):
		op.add_column(
			"roles",
			sa.Column(column_name, sa.Boolean(), server_default=sa.text("false"), nullable=False),
			schema="admins",
		)

	op.execute(
		sa.text(
			"""
			UPDATE admins.roles AS role
			SET can_manage_system_users = EXISTS (
					SELECT 1
					FROM admins.role_permissions AS role_permission
					JOIN admins.permissions AS permission ON permission.id = role_permission.permission_id
					WHERE role_permission.role_id = role.id
					  AND permission.name = 'admins.system_users.manage'
				),
				can_read_system_users = EXISTS (
					SELECT 1
					FROM admins.role_permissions AS role_permission
					JOIN admins.permissions AS permission ON permission.id = role_permission.permission_id
					WHERE role_permission.role_id = role.id
					  AND permission.name = 'admins.system_users.read'
				),
				can_manage_roles = EXISTS (
					SELECT 1
					FROM admins.role_permissions AS role_permission
					JOIN admins.permissions AS permission ON permission.id = role_permission.permission_id
					WHERE role_permission.role_id = role.id
					  AND permission.name = 'admins.roles.manage'
				),
				can_read_system_permissions = EXISTS (
					SELECT 1
					FROM admins.role_permissions AS role_permission
					JOIN admins.permissions AS permission ON permission.id = role_permission.permission_id
					WHERE role_permission.role_id = role.id
					  AND permission.name = 'admins.system_permissions.read'
				)
			"""
		)
	)

	for column_name in (
		"can_manage_members",
		"can_read_roles",
	):
		op.add_column(
			"community_roles",
			sa.Column(column_name, sa.Boolean(), server_default=sa.text("false"), nullable=False),
			schema="communities",
		)

	op.execute(
		sa.text(
			"""
			UPDATE communities.community_roles AS role
			SET can_manage_members = EXISTS (
					SELECT 1
					FROM communities.community_role_permissions AS role_permission
					JOIN communities.community_permissions AS permission
					  ON permission.id = role_permission.permission_id
					WHERE role_permission.role_id = role.id
					  AND permission.name = 'communities.members.manage'
				),
				can_read_roles = EXISTS (
					SELECT 1
					FROM communities.community_role_permissions AS role_permission
					JOIN communities.community_permissions AS permission
					  ON permission.id = role_permission.permission_id
					WHERE role_permission.role_id = role.id
					  AND permission.name = 'communities.roles.read'
				)
			"""
		)
	)

	for column_name in (
		"can_manage_system_users",
		"can_read_system_users",
		"can_manage_roles",
		"can_read_system_permissions",
	):
		op.alter_column(
			"roles",
			column_name,
			server_default=None,
			existing_type=sa.Boolean(),
			schema="admins",
		)

	for column_name in ("can_manage_members", "can_read_roles"):
		op.alter_column(
			"community_roles",
			column_name,
			server_default=None,
			existing_type=sa.Boolean(),
			schema="communities",
		)

	op.drop_table("role_permissions", schema="admins")
	op.drop_index(op.f("ix_admins_permissions_name"), table_name="permissions", schema="admins")
	op.drop_table("permissions", schema="admins")
	op.drop_table("community_role_permissions", schema="communities")
	op.drop_index(
		op.f("ix_communities_community_permissions_name"),
		table_name="community_permissions",
		schema="communities",
	)
	op.drop_table("community_permissions", schema="communities")


def downgrade() -> None:
	op.create_table(
		"permissions",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("name", sa.String(length=150), nullable=False),
		sa.Column("description", sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint("id"),
		schema="admins",
	)
	op.create_index(
		op.f("ix_admins_permissions_name"),
		"permissions",
		["name"],
		unique=True,
		schema="admins",
	)
	op.create_table(
		"role_permissions",
		sa.Column("role_id", sa.Uuid(), nullable=False),
		sa.Column("permission_id", sa.Uuid(), nullable=False),
		sa.ForeignKeyConstraint(["permission_id"], ["admins.permissions.id"], ondelete="CASCADE"),
		sa.ForeignKeyConstraint(["role_id"], ["admins.roles.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("role_id", "permission_id"),
		schema="admins",
	)

	op.create_table(
		"community_permissions",
		sa.Column("id", sa.Uuid(), nullable=False),
		sa.Column("name", sa.String(length=150), nullable=False),
		sa.PrimaryKeyConstraint("id"),
		schema="communities",
	)
	op.create_index(
		op.f("ix_communities_community_permissions_name"),
		"community_permissions",
		["name"],
		unique=True,
		schema="communities",
	)
	op.create_table(
		"community_role_permissions",
		sa.Column("role_id", sa.Uuid(), nullable=False),
		sa.Column("permission_id", sa.Uuid(), nullable=False),
		sa.ForeignKeyConstraint(
			["permission_id"],
			["communities.community_permissions.id"],
			ondelete="CASCADE",
		),
		sa.ForeignKeyConstraint(["role_id"], ["communities.community_roles.id"], ondelete="CASCADE"),
		sa.PrimaryKeyConstraint("role_id", "permission_id"),
		schema="communities",
	)

	for column_name in ("can_manage_system_users", "can_read_system_users", "can_manage_roles", "can_read_system_permissions"):
		op.drop_column("roles", column_name, schema="admins")
	for column_name in ("can_manage_members", "can_read_roles"):
		op.drop_column("community_roles", column_name, schema="communities")
