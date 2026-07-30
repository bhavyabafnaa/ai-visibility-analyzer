from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.database import get_session
from geolens_api.schemas.project import ProjectCreate, ProjectResponse
from geolens_api.services.projects import ProjectNotFoundError, ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, session: SessionDependency) -> ProjectResponse:
    project = await ProjectService(session).create(data)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, session: SessionDependency) -> ProjectResponse:
    try:
        project = await ProjectService(session).get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ProjectResponse]:
    projects = await ProjectService(session).list(offset=offset, limit=limit)
    return [ProjectResponse.model_validate(project) for project in projects]
