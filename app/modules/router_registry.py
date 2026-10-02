"""Route modules registered on the application under the shared API prefix."""

from importlib import import_module

from fastapi import FastAPI


API_V1_PREFIX = "/api/v1"

ROUTER_MODULES: tuple[str, ...] = (
	"app.modules.users.api.user_routes",
	"app.modules.admins.api.admin_routes",
	"app.modules.social_graph.api.user_routes",
	"app.modules.communities.api.user_routes",
	"app.modules.content.api.user_routes",
	"app.modules.content.api.admin_routes",
	"app.modules.notifications.api.user_routes",
)


def register_routers(app: FastAPI) -> None:
	"""Include each listed route module's router on the application."""
	for router_module in ROUTER_MODULES:
		module = import_module(router_module)
		app.include_router(module.router, prefix=API_V1_PREFIX)


__all__ = ["ROUTER_MODULES", "register_routers"]
