from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.shared.auth.dependencies import require_permission
from app.shared.dependencies.content_deps import get_content_service


router = APIRouter(tags=["content"])


@router.delete("/admin/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_post_as_system(
    post_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(require_permission(audience="system", permission="content.posts.delete"))],
    service: Annotated[Any, Depends(get_content_service)],
) -> Response:
    await service.delete_post(post_id, current_user["sub"], can_delete_any=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
