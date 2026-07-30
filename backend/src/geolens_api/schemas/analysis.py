from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from geolens_api.providers.contract import ProviderAvailability, ProviderResponse


class AnalysisStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class AnalysisStartRequest(BaseModel):
    providers: list[str] = Field(min_length=1, max_length=10)
    prompts: list[str] = Field(min_length=1, max_length=100)

    @field_validator("providers")
    @classmethod
    def normalize_providers(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        if any(not value for value in normalized):
            raise ValueError("provider names cannot be blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("provider names must be unique")
        return normalized

    @field_validator("prompts")
    @classmethod
    def normalize_prompts(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("prompts cannot be blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("prompts must be unique")
        return normalized


class PromptExecutionResponse(ProviderResponse):
    prompt: str


class AnalysisStartResponse(BaseModel):
    analysis_id: UUID
    status: AnalysisStatus
    started_at: datetime
    completed_at: datetime
    results: list[PromptExecutionResponse]


class ProviderAvailabilityResponse(ProviderAvailability):
    pass
