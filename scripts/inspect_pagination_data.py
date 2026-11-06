"""Inspect legacy data; optional visibility repair is explicit and transactional.

Run: python -m scripts.inspect_pagination_data [--normalize-visibility]
No rows are seeded or deleted. Duplicate pending pairs must be resolved by the
operator before upgrading the corrected unique index.
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import Connection, create_engine, text

from app.shared.config.settings import settings


def normalize_visibility(connection: Connection) -> int:
	result = connection.execute(text("""
		UPDATE communities.communities SET visibility = lower(visibility)
		WHERE visibility IN ('PUBLIC', 'PRIVATE')
	"""))
	return result.rowcount


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--normalize-visibility", action="store_true")
	args = parser.parse_args()
	engine = create_engine(settings.MIGRATION_DATABASE_URL)
	try:
		with engine.begin() as connection:
			if args.normalize_visibility:
				print(f"Normalized legacy visibility rows: {normalize_visibility(connection)}")
			for table, column in (("communities.communities", "visibility"),
					("social_graph.friend_requests", "status")):
				rows = connection.execute(text(
					f"SELECT {column}, count(*) FROM {table} GROUP BY {column} ORDER BY {column}"
				)).all()
				print(f"{table}.{column}: {json.dumps([list(row) for row in rows])}")
			duplicates = connection.scalar(text("""
				SELECT count(*) FROM (
					SELECT least(requester_id, receiver_id), greatest(requester_id, receiver_id)
					FROM social_graph.friend_requests WHERE status = 'PENDING'
					GROUP BY 1, 2 HAVING count(*) > 1
				) pairs
			"""))
			print(f"Duplicate pending pairs: {duplicates}")
	finally:
		engine.dispose()


if __name__ == "__main__":
	main()
