from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from geolens_api.config import get_settings
from geolens_api.database import engine
from geolens_api.providers.registry import ProviderRegistry
from geolens_api.routers import (
    analyses_router,
    crawls_router,
    projects_router,
    system_router,
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    registry = ProviderRegistry.from_settings(get_settings())
    application.state.provider_registry = registry
    try:
        yield
    finally:
        await registry.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description="AI visibility and citation intelligence API.",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.include_router(system_router)
    application.include_router(projects_router)
    application.include_router(crawls_router)
    application.include_router(analyses_router)
    return application


app = create_app()
