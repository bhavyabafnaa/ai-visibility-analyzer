from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SiteCreate(BaseModel):
    url: HttpUrl


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    site: SiteCreate | None = None
    competitors: list[CompetitorCreate] = Field(default_factory=list, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


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
    created_at: datetime
    updated_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    site: SiteResponse | None
    competitors: list[CompetitorResponse]
    created_at: datetime
    updated_at: datetime
