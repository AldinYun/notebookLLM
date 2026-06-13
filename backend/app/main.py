from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.notebooks import router as notebooks_router
from app.api.rag import router as rag_router
from app.api.search import router as search_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.include_router(notebooks_router, prefix="/notebooks", tags=["notebooks"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(search_router, prefix="/search", tags=["search"])
    app.include_router(rag_router, prefix="/rag", tags=["rag"])
    app.include_router(health_router, prefix="/health", tags=["health"])
    return app


app = create_app()
