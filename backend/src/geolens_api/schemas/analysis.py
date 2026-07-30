from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from geolens_api.providers.contract import ProviderAvailability, ProviderResponse


class AnalysisStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class AnalysisStartRequest(BaseModel):
    providers: list[str] = Field(min_length=1, max_length=10)
    prompts: list[str] = Field(min_length=1, max_length=100)
    project_id: UUID | None = None
    crawl_job_id: UUID | None = None
    claim_classifier_provider: str | None = None

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

    @field_validator("claim_classifier_provider")
    @classmethod
    def normalize_classifier_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("claim_classifier_provider cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_persistence_options(self) -> "AnalysisStartRequest":
        if self.project_id is None and (
            self.crawl_job_id is not None or self.claim_classifier_provider is not None
        ):
            raise ValueError("project_id is required for crawl evidence or claim classification")
        return self


class PromptExecutionResponse(ProviderResponse):
    prompt: str


class AnalysisStartResponse(BaseModel):
    analysis_id: UUID
    status: AnalysisStatus
    started_at: datetime
    completed_at: datetime
    results: list[PromptExecutionResponse]
    persisted: bool = False


class ProviderAvailabilityResponse(ProviderAvailability):
    pass


class AnalysisCitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_id: UUID
    ordinal: int
    url: str
    normalized_domain: str | None
    title: str | None
    start_index: int | None
    end_index: int | None
    cited_text: str | None
    published_at: str | None
    normalization_rule_version: str


class AnalysisEntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_id: UUID
    entity_key: str
    name: str
    kind: str
    matched_aliases: list[str]
    mention_count: int
    first_mention_start: int
    first_mention_relative: float
    position_bucket: str
    mentions: list[dict[str, object]]
    extraction_method: str
    extraction_rule_version: str


class AnalysisScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_run_id: UUID
    name: str
    numerator: float
    denominator: float
    value: float | None
    percentage: float | None
    is_defined: bool
    method: str
    rule_version: str
    is_objective_truth: bool | None
    disclaimer: str | None


class ClaimEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: str
    source_id: UUID
    source_reference: str
    url: str | None
    excerpt: str
    relevance_score: float
    retrieval_rule_version: str


class AnalysisClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_id: UUID
    ordinal: int
    claim_text: str
    start_index: int
    end_index: int
    classification: str
    confidence: float
    explanation: str
    classifier: str
    model_identifier: str | None
    segmentation_rule_version: str
    evidence: list[ClaimEvidenceResponse]
