from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from geolens_api.providers.registry import (
    ProviderRegistry,
    UnknownProviderError,
)
from geolens_api.schemas.analysis import (
    AnalysisStartRequest,
    AnalysisStartResponse,
    ProviderAvailabilityResponse,
)
from geolens_api.services.analyses import AnalysisService

router = APIRouter(tags=["analyses"])


def get_provider_registry(request: Request) -> ProviderRegistry:
    registry = getattr(request.app.state, "provider_registry", None)
    if not isinstance(registry, ProviderRegistry):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Provider registry is not initialized",
        )
    return registry


ProviderRegistryDependency = Annotated[ProviderRegistry, Depends(get_provider_registry)]


@router.get("/providers", response_model=list[ProviderAvailabilityResponse])
async def list_providers(
    registry: ProviderRegistryDependency,
) -> list[ProviderAvailabilityResponse]:
    return [
        ProviderAvailabilityResponse.model_validate(item.model_dump())
        for item in registry.availability()
    ]


@router.post(
    "/analyses",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_analysis(
    data: AnalysisStartRequest,
    registry: ProviderRegistryDependency,
) -> AnalysisStartResponse:
    try:
        return await AnalysisService(registry).start(data)
    except UnknownProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
