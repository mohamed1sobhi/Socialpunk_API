"""Signed, scoped keyset cursors; no SQL, Pydantic, or domain dependencies."""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hmac
import json
from typing import Any
from uuid import UUID

from app.shared.exceptions.handlers import ValidationError


class CursorPaginator:
	def __init__(self, secret: str) -> None:
		self._key = hmac.digest(secret.encode(), b"socialpunk-pagination-v1", "sha256")

	@staticmethod
	def limit(value: int, *, maximum: int = 100) -> int:
		if type(value) is not int or not 1 <= value <= maximum:
			raise ValidationError(f"Limit must be between 1 and {maximum}")
		return value

	@staticmethod
	def _encode_bytes(value: bytes) -> str:
		return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

	@staticmethod
	def _decode_bytes(value: str) -> bytes:
		return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

	def decode(self, token: str | None, scope: str, *, timestamp: bool = True) -> tuple[datetime, UUID] | UUID | None:
		if token is None:
			return None
		try:
			if not isinstance(token, str) or not 1 <= len(token) <= 2048:
				raise ValueError
			body, signature = token.split(".")
			if not hmac.compare_digest(self._decode_bytes(signature), hmac.digest(self._key, body.encode("ascii"), "sha256")):
				raise ValueError
			payload = json.loads(self._decode_bytes(body))
			if not isinstance(payload, list) or len(payload) != 4 or type(payload[0]) is not int or payload[:2] != [1, scope]:
				raise ValueError
			if not isinstance(payload[3], str):
				raise ValueError
			row_id = UUID(payload[3])
			if not timestamp:
				if payload[2] is not None:
					raise ValueError
				return row_id
			if not isinstance(payload[2], str):
				raise ValueError
			created_at = datetime.fromisoformat(payload[2])
			if created_at.tzinfo is None or created_at.utcoffset() is None:
				raise ValueError
			return created_at.astimezone(timezone.utc), row_id
		except (ValueError, TypeError, UnicodeError, binascii.Error, OverflowError) as exc:
			raise ValidationError("Invalid cursor or cursor scope") from exc

	def page(
		self, rows: list[dict[str, Any]], limit: int, scope: str, *,
		time_field: str | None = "created_at", id_field: str = "id",
	) -> tuple[list[dict[str, Any]], dict[str, Any]]:
		has_more = len(rows) > limit
		items = rows[:limit]
		next_cursor = None
		if has_more:
			last = items[-1]
			timestamp = last[time_field].astimezone(timezone.utc).isoformat(timespec="microseconds") if time_field else None
			body = self._encode_bytes(json.dumps([1, scope, timestamp, str(last[id_field])], separators=(",", ":")).encode())
			next_cursor = body + "." + self._encode_bytes(hmac.digest(self._key, body.encode("ascii"), "sha256"))
		return items, {"next_cursor": next_cursor, "has_more": has_more}
