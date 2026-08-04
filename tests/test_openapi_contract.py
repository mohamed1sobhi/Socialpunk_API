from __future__ import annotations

from app.main import app


def test_create_post_openapi_contract_is_community_scoped() -> None:
	schema = app.openapi()
	request_schema = schema["components"]["schemas"]["CreatePostRequest"]
	response_schema = schema["components"]["schemas"]["PostResponse"]

	assert set(request_schema["required"]) == {"community_id", "body"}
	assert "visibility" not in request_schema["properties"]
	assert "visibility" not in response_schema["properties"]
