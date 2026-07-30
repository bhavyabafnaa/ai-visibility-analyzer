import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from geolens_api.providers.contract import (
    Provider,
    ProviderError,
    ProviderResolver,
    ProviderResponse,
    ProviderResponseStatus,
)
from geolens_api.schemas.analysis import (
    AnalysisStartRequest,
    AnalysisStartResponse,
    AnalysisStatus,
    PromptExecutionResponse,
)


class AnalysisService:
    """Executes a prompt matrix using only the provider-neutral contract."""

    def __init__(self, registry: ProviderResolver) -> None:
        self._registry = registry

    async def start(self, data: AnalysisStartRequest) -> AnalysisStartResponse:
        providers = [self._registry.get(name) for name in data.providers]
        executions = [
            self._execute(provider, prompt) for provider in providers for prompt in data.prompts
        ]
        started_at = datetime.now(timezone.utc)
        results = await asyncio.gather(*executions)
        completed_at = datetime.now(timezone.utc)
        return AnalysisStartResponse(
            analysis_id=uuid4(),
            status=self._analysis_status(results),
            started_at=started_at,
            completed_at=completed_at,
            results=results,
        )

    @staticmethod
    async def _execute(provider: Provider, prompt: str) -> PromptExecutionResponse:
        try:
            result = await provider.execute(prompt)
        except Exception as error:
            result = ProviderResponse(
                provider=provider.name,
                model_identifier=provider.model_identifier,
                response_text="",
                raw_response={},
                latency_ms=0,
                status=ProviderResponseStatus.ERROR,
                error=ProviderError(
                    code="provider_execution_error",
                    message=str(error) or "Provider execution failed",
                    retryable=False,
                    attempts=1,
                ),
            )
        return PromptExecutionResponse(prompt=prompt, **result.model_dump())

    @staticmethod
    def _analysis_status(results: list[PromptExecutionResponse]) -> AnalysisStatus:
        success_count = sum(result.status is ProviderResponseStatus.SUCCEEDED for result in results)
        if success_count == len(results):
            return AnalysisStatus.SUCCEEDED
        if success_count:
            return AnalysisStatus.COMPLETED_WITH_ERRORS
        return AnalysisStatus.FAILED
