"""Create the idempotent project used by the local MockProvider demo."""

import asyncio

from geolens_api.database import async_session_factory, engine
from geolens_api.demo import (
    DEMO_COMPETITORS,
    DEMO_PROJECT_ALIASES,
    DEMO_PROJECT_NAME,
    DEMO_SITE_URL,
)
from geolens_api.repositories.projects import ProjectRepository
from geolens_api.schemas.project import ProjectCreate
from geolens_api.services.projects import ProjectService


async def seed_demo() -> None:
    async with async_session_factory() as session:
        existing = await ProjectRepository(session).get_by_name(DEMO_PROJECT_NAME)
        if existing is not None:
            print(f"Demo project already exists: {existing.id}")
            return

        project = await ProjectService(session).create(
            ProjectCreate.model_validate(
                {
                    "name": DEMO_PROJECT_NAME,
                    "aliases": DEMO_PROJECT_ALIASES,
                    "site": {"url": DEMO_SITE_URL},
                    "competitors": DEMO_COMPETITORS,
                }
            )
        )
        print(f"Created demo project: {project.id}")


async def _main() -> None:
    try:
        await seed_demo()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
