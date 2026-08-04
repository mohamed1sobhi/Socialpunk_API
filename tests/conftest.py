from __future__ import annotations

import os


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/socialpunk_test")
os.environ.setdefault("MIGRATION_DATABASE_URL", "postgresql://postgres:postgres@localhost/socialpunk_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
