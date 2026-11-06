from __future__ import annotations

import os
import importlib
from uuid import uuid4

import pytest
import pytest_asyncio

from app.shared.config.settings import settings


os.environ.setdefault("DATABASE_URL", settings.DATABASE_URL)
os.environ.setdefault("MIGRATION_DATABASE_URL", settings.MIGRATION_DATABASE_URL)
os.environ.setdefault("TEST_DATABASE_URL", settings.TEST_DATABASE_URL)
os.environ.setdefault("SECRET_KEY", "test-secret-key")


@pytest_asyncio.fixture
async def pg_session():
	"""Use unique, transaction-local schemas, never application tables.

	TEST_DATABASE_URL must be an asyncpg URL. Everything, including schema DDL
	and commits performed by services, is rolled back at fixture teardown.
	"""
	url = os.environ.get("TEST_DATABASE_URL")
	if not url:
		pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
	from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
	from sqlalchemy.schema import CreateSchema
	from app.modules.model_registry import MODEL_MODULES
	from app.shared.database.base import ALL_METADATA, SCHEMA_NAMES
	for module in MODEL_MODULES:
		importlib.import_module(module)
	prefix = f"pagination_test_{uuid4().hex[:12]}"
	schemas = {name: f"{prefix}_{name}" for name in SCHEMA_NAMES}
	engine = create_async_engine(url, execution_options={"schema_translate_map": schemas})
	try:
		async with engine.connect() as connection:
			transaction = await connection.begin()
			try:
				for schema in schemas.values():
					await connection.execute(CreateSchema(schema))
				for metadata in ALL_METADATA:
					await connection.run_sync(metadata.create_all)
				async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
					yield session
			finally:
				await transaction.rollback()
	finally:
		await engine.dispose()
