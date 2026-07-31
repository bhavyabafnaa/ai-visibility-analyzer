import asyncio
from uuid import UUID

from geolens_api.celery_app import celery_app
from geolens_api.config import get_settings
from geolens_api.database import async_session_factory, engine
from geolens_api.providers.registry import ProviderRegistry
from geolens_api.services.analyses import AnalysisService


@celery_app.task(name="geolens.run_analysis")
def run_analysis(analysis_id: str) -> None:
    asyncio.run(_run_analysis(UUID(analysis_id)))


async def _run_analysis(analysis_id: UUID) -> None:
    registry = ProviderRegistry.from_settings(get_settings())
    try:
        async with async_session_factory() as session:
            await AnalysisService(registry, session).execute(analysis_id)
    finally:
        await registry.aclose()
        await engine.dispose()
