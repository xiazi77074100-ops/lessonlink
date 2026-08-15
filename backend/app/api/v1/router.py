from fastapi import APIRouter

from app.api.v1.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
