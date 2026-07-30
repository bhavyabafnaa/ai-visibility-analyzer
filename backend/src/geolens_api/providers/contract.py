from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator


class ProviderResponseStatus(str, Enum):
    """Terminal outcome of one provider prompt execution."""

    SUCCEEDED = "succeeded"
    ERROR = "error"
    TIMED_OUT = "timed_out"
    RATE_LIMITED = "rate_limited"
    DISABLED = "disabled"


class Citation(BaseModel):
    """Provider-neutral source reference."""

    url: str = Field(min_length=1)
    title: str | None = None
    start_index: int | None = Field(default=None, ge=0)
    end_index: int | None = Field(default=None, ge=0)
    cited_text: str | None = None
    published_at: str | None = None

    @model_validator(mode="after")
    def validate_text_range(self) -> "Citation":
        if (
            self.start_index is not None
            and self.end_index is not None
            and self.end_index < self.start_index
        ):
            raise ValueError("citation end_index must not precede start_index")
        return self


class TokenUsage(BaseModel):
    """Token counts normalized across provider response formats."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)


class ProviderError(BaseModel):
    """Structured error information safe to expose at the API boundary."""

    code: str
    message: str
    retryable: bool
    http_status: int | None = None
    attempts: int = Field(default=1, ge=0)


class ProviderResponse(BaseModel):
    """Common result returned by every model provider adapter."""

    provider: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    response_text: str
    citations: list[Citation] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = Field(ge=0)
    status: ProviderResponseStatus
    error: ProviderError | None = None

    @model_validator(mode="after")
    def validate_error_matches_status(self) -> "ProviderResponse":
        succeeded = self.status is ProviderResponseStatus.SUCCEEDED
        if succeeded and self.error is not None:
            raise ValueError("successful provider responses cannot contain error information")
        if not succeeded and self.error is None:
            raise ValueError("unsuccessful provider responses require error information")
        return self


class ProviderAvailability(BaseModel):
    name: str
    model_identifier: str
    enabled: bool
    disabled_reason: str | None


@runtime_checkable
class Provider(Protocol):
    """Interface consumed by analysis orchestration."""

    @property
    def name(self) -> str: ...

    @property
    def model_identifier(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    @property
    def disabled_reason(self) -> str | None: ...

    async def execute(self, prompt: str) -> ProviderResponse: ...


class ProviderResolver(Protocol):
    """Provider lookup boundary used by application orchestration."""

    def get(self, provider_name: str) -> Provider: ...
