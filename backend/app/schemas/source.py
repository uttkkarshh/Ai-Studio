from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    title: str
    url: str | None = None
    source_type: str
    content: str | None = None
    metadata: dict[str, Any] | None = None
    part_ids: list[int] = Field(default_factory=list)


class SourceUpdate(BaseModel):
    title: str | None = None
    url: str | None = None
    source_type: str | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None
    part_ids: list[int] | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    url: str | None
    source_type: str
    content: str | None
    metadata: dict[str, Any] | None = Field(validation_alias="metadata_")
    part_ids: list[int]
    created_at: datetime
    updated_at: datetime
