from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from geolens_api.models.competitor import Competitor
from geolens_api.models.project import Project
from geolens_api.models.site import Site
from geolens_api.schemas.project import ProjectCreate


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ProjectCreate) -> Project:
        project = Project(name=data.name)
        if data.site is not None:
            project.site = Site(url=str(data.site.url))
        project.competitors = [
            Competitor(name=competitor.name, url=str(competitor.url))
            for competitor in data.competitors
        ]
        self._session.add(project)
        await self._session.flush()
        return project

    async def get(self, project_id: UUID) -> Project | None:
        statement = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.site),
                selectinload(Project.competitors),
            )
        )
        return await self._session.scalar(statement)

    async def list(self, *, offset: int, limit: int) -> list[Project]:
        statement = (
            select(Project)
            .options(
                selectinload(Project.site),
                selectinload(Project.competitors),
            )
            .order_by(Project.created_at.desc(), Project.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def count(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(Project)) or 0)
