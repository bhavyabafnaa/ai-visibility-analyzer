from geolens_api.routers.analyses import router as analyses_router
from geolens_api.routers.crawls import router as crawls_router
from geolens_api.routers.projects import router as projects_router
from geolens_api.routers.system import router as system_router

__all__ = ["analyses_router", "crawls_router", "projects_router", "system_router"]
