from typing import Any

import httpx

from geolens_api.config import Settings
from geolens_api.providers.contract import (
    Provider,
    ProviderAvailability,
    ProviderError,
    ProviderResponse,
    ProviderResponseStatus,
    TokenUsage,
)
from geolens_api.providers.gemini import GeminiProvider
from geolens_api.providers.mock import MockProvider
from geolens_api.providers.openai import OpenAIProvider
from geolens_api.providers.perplexity import PerplexityProvider


class UnknownProviderError(LookupError):
    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Unknown provider: {provider_name}")
        self.provider_name = provider_name


class DisabledProvider:
    """Explicit provider placeholder used when its credential is absent."""

    def __init__(self, *, name: str, model_identifier: str, reason: str) -> None:
        self._name = name
        self._model_identifier = model_identifier
        self._reason = reason

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def enabled(self) -> bool:
        return False

    @property
    def disabled_reason(self) -> str:
        return self._reason

    async def execute(self, prompt: str) -> ProviderResponse:
        del prompt
        return ProviderResponse(
            provider=self.name,
            model_identifier=self.model_identifier,
            response_text="",
            raw_response={"disabled_reason": self.disabled_reason},
            token_usage=TokenUsage(),
            latency_ms=0,
            status=ProviderResponseStatus.DISABLED,
            error=ProviderError(
                code="provider_disabled",
                message=self.disabled_reason,
                retryable=False,
                attempts=0,
            ),
        )


class ProviderRegistry:
    """Owns backend provider instances and their HTTP client lifecycles."""

    def __init__(
        self,
        providers: list[Provider],
        *,
        clients: list[httpx.AsyncClient] | None = None,
    ) -> None:
        self._providers = {provider.name: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ValueError("provider names must be unique")
        self._clients = clients or []

    @classmethod
    def from_settings(cls, settings: Settings) -> "ProviderRegistry":
        providers: list[Provider] = [
            MockProvider(model_identifier=settings.mock_model),
        ]
        clients: list[httpx.AsyncClient] = []
        shared_arguments: dict[str, Any] = {
            "timeout_seconds": settings.provider_timeout_seconds,
            "max_retries": settings.provider_max_retries,
            "retry_backoff_seconds": settings.provider_retry_backoff_seconds,
            "max_retry_after_seconds": settings.provider_max_retry_after_seconds,
        }

        openai_key = cls._credential_value(settings.openai_api_key)
        if openai_key is None:
            providers.append(
                DisabledProvider(
                    name="openai",
                    model_identifier=settings.openai_model,
                    reason="OPENAI_API_KEY is not configured",
                )
            )
        else:
            client = httpx.AsyncClient()
            clients.append(client)
            providers.append(
                OpenAIProvider(
                    model_identifier=settings.openai_model,
                    api_key=openai_key,
                    client=client,
                    base_url=str(settings.openai_base_url),
                    **shared_arguments,
                )
            )

        gemini_key = cls._credential_value(settings.gemini_api_key)
        if gemini_key is None:
            providers.append(
                DisabledProvider(
                    name="gemini",
                    model_identifier=settings.gemini_model,
                    reason="GEMINI_API_KEY is not configured",
                )
            )
        else:
            client = httpx.AsyncClient()
            clients.append(client)
            providers.append(
                GeminiProvider(
                    model_identifier=settings.gemini_model,
                    api_key=gemini_key,
                    client=client,
                    base_url=str(settings.gemini_base_url),
                    **shared_arguments,
                )
            )

        perplexity_key = cls._credential_value(settings.perplexity_api_key)
        if perplexity_key is None:
            providers.append(
                DisabledProvider(
                    name="perplexity",
                    model_identifier=settings.perplexity_model,
                    reason="PERPLEXITY_API_KEY is not configured",
                )
            )
        else:
            client = httpx.AsyncClient()
            clients.append(client)
            providers.append(
                PerplexityProvider(
                    model_identifier=settings.perplexity_model,
                    api_key=perplexity_key,
                    client=client,
                    base_url=str(settings.perplexity_base_url),
                    **shared_arguments,
                )
            )

        return cls(providers, clients=clients)

    def get(self, provider_name: str) -> Provider:
        try:
            return self._providers[provider_name]
        except KeyError as error:
            raise UnknownProviderError(provider_name) from error

    def availability(self) -> list[ProviderAvailability]:
        return [
            ProviderAvailability(
                name=provider.name,
                model_identifier=provider.model_identifier,
                enabled=provider.enabled,
                disabled_reason=provider.disabled_reason,
            )
            for provider in self._providers.values()
        ]

    async def aclose(self) -> None:
        for client in self._clients:
            await client.aclose()

    @staticmethod
    def _credential_value(secret: object) -> str | None:
        get_secret_value = getattr(secret, "get_secret_value", None)
        if not callable(get_secret_value):
            return None
        value = str(get_secret_value()).strip()
        return value or None
