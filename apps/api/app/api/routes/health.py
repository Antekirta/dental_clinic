from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check")
def health_check() -> dict[str, str]:
    print(settings.app_name)
    return {"status": "ok"}
