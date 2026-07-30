from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.database import get_session
from geolens_api.providers.registry import (
    ProviderRegistry,
    UnknownProviderError,
)
from geolens_api.schemas.analysis import (
    AnalysisCitationResponse,
    AnalysisClaimResponse,
    AnalysisEntityResponse,
    AnalysisScoreResponse,
    AnalysisStartRequest,
    AnalysisStartResponse,
    ProviderAvailabilityResponse,
)
from geolens_api.services.analyses import (
    AnalysisCrawlNotFoundError,
    AnalysisCrawlProjectMismatchError,
    AnalysisNotFoundError,
    AnalysisProjectNotFoundError,
    AnalysisResultsService,
    AnalysisService,
)

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
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


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
    session: SessionDependency,
) -> AnalysisStartResponse:
    try:
        return await AnalysisService(registry, session).start(data)
    except UnknownProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except (AnalysisProjectNotFoundError, AnalysisCrawlNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except AnalysisCrawlProjectMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.get(
    "/analyses/{analysis_id}/citations",
    response_model=list[AnalysisCitationResponse],
)
async def list_analysis_citations(
    analysis_id: UUID,
    session: SessionDependency,
) -> list[AnalysisCitationResponse]:
    try:
        citations = await AnalysisResultsService(session).citations(analysis_id)
    except AnalysisNotFoundError as error:
        raise _analysis_not_found(error) from error
    return [AnalysisCitationResponse.model_validate(citation) for citation in citations]


@router.get(
    "/analyses/{analysis_id}/entities",
    response_model=list[AnalysisEntityResponse],
)
async def list_analysis_entities(
    analysis_id: UUID,
    session: SessionDependency,
) -> list[AnalysisEntityResponse]:
    try:
        entities = await AnalysisResultsService(session).entities(analysis_id)
    except AnalysisNotFoundError as error:
        raise _analysis_not_found(error) from error
    return [AnalysisEntityResponse.model_validate(entity) for entity in entities]


@router.get(
    "/analyses/{analysis_id}/scores",
    response_model=list[AnalysisScoreResponse],
)
async def list_analysis_scores(
    analysis_id: UUID,
    session: SessionDependency,
) -> list[AnalysisScoreResponse]:
    try:
        scores = await AnalysisResultsService(session).scores(analysis_id)
    except AnalysisNotFoundError as error:
        raise _analysis_not_found(error) from error
    return [AnalysisScoreResponse.model_validate(score) for score in scores]


@router.get(
    "/analyses/{analysis_id}/claims",
    response_model=list[AnalysisClaimResponse],
)
async def list_analysis_claims(
    analysis_id: UUID,
    session: SessionDependency,
) -> list[AnalysisClaimResponse]:
    try:
        claims = await AnalysisResultsService(session).claims(analysis_id)
    except AnalysisNotFoundError as error:
        raise _analysis_not_found(error) from error
    return [AnalysisClaimResponse.model_validate(claim) for claim in claims]


def _analysis_not_found(error: AnalysisNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )
