"""Exercise real migration SQL against transaction-local PostgreSQL schemas."""
from __future__ import annotations

import importlib.util
from io import StringIO
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.schema import CreateSchema

from app.shared.database.base import SCHEMA_NAMES


def migration_sql(filename: str, schemas: dict[str, str], *, downgrade: bool = False) -> str:
	path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
	spec = importlib.util.spec_from_file_location("pagination_test_revision", path)
	assert spec and spec.loader
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	output = StringIO()
	context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
	with Operations.context(context):
		(module.downgrade if downgrade else module.upgrade)()
	# Only rewrite schema-qualified identifiers, not quoted permission names.
	return re.sub(r"(?<!['\w])(users|admins|social_graph|communities|content|notifications)\.",
		lambda match: schemas[match[1]] + ".", output.getvalue())


def test_upgrade_preflights_legacy_data_enforces_uniqueness_and_downgrades() -> None:
	url = os.environ.get("TEST_DATABASE_URL")
	if not url:
		pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL migration tests")
	schemas = {name: f"migration_test_{uuid4().hex[:12]}_{name}" for name in SCHEMA_NAMES}
	engine = create_engine(make_url(url).set(drivername="postgresql+psycopg2"))
	try:
		with engine.connect() as connection:
			transaction = connection.begin()
			try:
				for schema in schemas.values():
					connection.execute(CreateSchema(schema))
				for revision in ("807c9b761246_init_migrations.py", "4f31c98d27ab_make_posts_community_scoped.py",
						"b2d4e6f8a901_replace_permissions_with_role_flags.py", "c3a51b8e6294_add_admin_post_delete_flag.py"):
					connection.exec_driver_sql(migration_sql(revision, schemas))
				community_table = schemas["communities"] + ".communities"
				requests_table = schemas["social_graph"] + ".friend_requests"
				connection.execute(text(f"INSERT INTO {community_table} (id, name, owner_id, created_at, visibility) VALUES (:id, 'Legacy', :owner, now(), 'PUBLIC')"),
					{"id": uuid4(), "owner": uuid4()})
				revision = "d7e9a102bc34_add_pagination_indexes.py"
				with pytest.raises(DBAPIError, match="normalize-visibility"):
					with connection.begin_nested():
						connection.exec_driver_sql(migration_sql(revision, schemas))
				# The explicit repair command uses this same SQL; migrations do not repair data.
				connection.execute(text(f"UPDATE {community_table} SET visibility = lower(visibility) WHERE visibility IN ('PUBLIC', 'PRIVATE')"))
				a, b = uuid4(), uuid4()
				insert_request = text(f"INSERT INTO {requests_table} (id, requester_id, receiver_id, status, created_at, updated_at) VALUES (:id, :a, :b, 'PENDING', now(), now())")
				connection.execute(insert_request, {"id": uuid4(), "a": a, "b": b})
				duplicate_id = uuid4()
				connection.execute(insert_request, {"id": duplicate_id, "a": b, "b": a})
				with pytest.raises(DBAPIError, match="duplicate pending pairs"):
					with connection.begin_nested():
						connection.exec_driver_sql(migration_sql(revision, schemas))
				connection.execute(text(f"DELETE FROM {requests_table} WHERE id = :id"), {"id": duplicate_id})
				connection.exec_driver_sql(migration_sql(revision, schemas))
				with pytest.raises(IntegrityError):
					with connection.begin_nested():
						connection.execute(insert_request, {"id": uuid4(), "a": b, "b": a})
				indexes = {row["name"]: row for row in inspect(connection).get_indexes("friend_requests", schema=schemas["social_graph"])}
				assert "PENDING" in str(indexes["uq_friend_requests_pending_pair"].get("dialect_options"))
				assert "ix_friend_requests_receiver_cursor" in indexes
				assert "ix_posts_feed_cursor" in {row["name"] for row in inspect(connection).get_indexes("posts", schema=schemas["content"])}
				connection.exec_driver_sql(migration_sql(revision, schemas, downgrade=True))
				assert "ix_posts_feed_cursor" not in {row["name"] for row in inspect(connection).get_indexes("posts", schema=schemas["content"])}
				assert connection.scalar(text(f"SELECT visibility FROM {community_table}")) == "public"
			finally:
				transaction.rollback()
	finally:
		engine.dispose()
