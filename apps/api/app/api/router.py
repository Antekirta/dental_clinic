from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.modules.contacts.api import router as contacts_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(contacts_router)
