from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.database import get_session
from geolens_api.schemas.system import HealthResponse, ReadinessResponse
from geolens_api.services.system import SystemService

router = APIRouter(tags=["system"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process-level API health."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(response: Response, session: SessionDependency) -> ReadinessResponse:
    """Report whether the API can execute a query against PostgreSQL."""
    if not await SystemService(session).database_is_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable")
    return ReadinessResponse(status="ok")
