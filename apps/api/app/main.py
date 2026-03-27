from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings


def create_application() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.app_debug)
    app.include_router(api_router)
    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host or "0.0.0.0",
        port=settings.app_port,
        reload=True,
    )
