from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SiteCreate(BaseModel):
    url: HttpUrl


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    aliases: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: list[str]) -> list[str]:
        return _normalize_aliases(values)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    site: SiteCreate | None = None
    competitors: list[CompetitorCreate] = Field(default_factory=list, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: list[str]) -> list[str]:
        return _normalize_aliases(values)


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    url: str
    created_at: datetime
    updated_at: datetime


class CompetitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    url: str
    aliases: list[str]
    created_at: datetime
    updated_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    aliases: list[str]
    site: SiteResponse | None
    competitors: list[CompetitorResponse]
    created_at: datetime
    updated_at: datetime


def _normalize_aliases(values: list[str]) -> list[str]:
    normalized = [value.strip() for value in values]
    if any(not value for value in normalized):
        raise ValueError("aliases cannot be blank")
    if any(len(value) > 200 for value in normalized):
        raise ValueError("aliases cannot exceed 200 characters")
    casefolded = [value.casefold() for value in normalized]
    if len(casefolded) != len(set(casefolded)):
        raise ValueError("aliases must be unique")
    return normalized
