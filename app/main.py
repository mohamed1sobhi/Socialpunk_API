from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.modules.router_registry import register_routers
from app.shared.exceptions.handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 10: register startup singletons such as notification listeners here.
    yield
    # Phase 10: teardown (e.g. close DB connections) here


app = FastAPI(
    title="Social Media API",
    version="1.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
register_routers(app)
