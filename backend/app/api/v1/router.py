from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.children import router as children_router
from app.api.v1.events import router as events_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.parents import router as parents_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(children_router)
router.include_router(events_router)
router.include_router(organizations_router)
router.include_router(parents_router)


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
