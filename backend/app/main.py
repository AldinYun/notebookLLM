from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.notebooks import router as notebooks_router
from app.api.profiles import router as profiles_router
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(notebooks_router, prefix="/notebooks", tags=["notebooks"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(models_router, prefix="/models", tags=["models"])
    app.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
    app.include_router(search_router, prefix="/search", tags=["search"])
    app.include_router(rag_router, prefix="/rag", tags=["rag"])
    app.include_router(health_router, prefix="/health", tags=["health"])
    return app


app = create_app()
