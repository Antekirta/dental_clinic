from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings


def create_application() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.app_debug)
    app.include_router(api_router)
    return app


app = create_application()
