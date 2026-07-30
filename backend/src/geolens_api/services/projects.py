from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.models.project import Project
from geolens_api.repositories.projects import ProjectRepository
from geolens_api.schemas.project import ProjectCreate


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"Project {project_id} was not found")
        self.project_id = project_id


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._projects = ProjectRepository(session)

    async def create(self, data: ProjectCreate) -> Project:
        project = await self._projects.create(data)
        await self._session.commit()
        return project

    async def get(self, project_id: UUID) -> Project:
        project = await self._projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    async def list(self, *, offset: int, limit: int) -> list[Project]:
        return await self._projects.list(offset=offset, limit=limit)
