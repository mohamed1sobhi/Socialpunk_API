from fastapi import APIRouter

from app.modules.content.api.admin_routes import router as admin_router
from app.modules.content.api.user_routes import router as user_router

router = APIRouter()
router.include_router(user_router)
router.include_router(admin_router)

__all__ = ["router"]
