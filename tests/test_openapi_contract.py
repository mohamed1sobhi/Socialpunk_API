from __future__ import annotations

from app.main import app


def test_create_post_openapi_contract_is_community_scoped() -> None:
	schema = app.openapi()
	request_schema = schema["components"]["schemas"]["CreatePostRequest"]
	response_schema = schema["components"]["schemas"]["PostResponse"]

	assert set(request_schema["required"]) == {"community_id", "body"}
	assert "visibility" not in request_schema["properties"]
	assert "visibility" not in response_schema["properties"]


def test_role_permission_api_contract_uses_fixed_flags() -> None:
	schema = app.openapi()
	paths = schema["paths"]
	role_schema = schema["components"]["schemas"]["RoleResponse"]

	assert "/api/v1/admins/permissions" not in paths
	assert "/api/v1/admins/roles/{role_id}/permissions" not in paths
	assert {"get", "post"}.issubset(paths["/api/v1/admins/roles"])
	assert "patch" in paths["/api/v1/admins/roles/{role_id}"]
	assert {
		"can_manage_system_users",
		"can_read_system_users",
		"can_manage_roles",
		"can_read_system_permissions",
	}.issubset(role_schema["properties"])

	community_role_schema = schema["components"]["schemas"]["CommunityRoleResponse"]
	community_permission_schema = schema["components"]["schemas"]["CommunityPermissionResponse"]
	assert set(community_role_schema["properties"]) == {"id", "name", "permission_names"}
	assert set(community_permission_schema["properties"]) == {"id", "name"}
