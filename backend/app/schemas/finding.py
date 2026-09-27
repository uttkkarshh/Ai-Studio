from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FindingCreatedByType = Literal["user", "ai", "imported"]
FindingStatus = Literal["draft", "active", "archived"]


class FindingCreate(BaseModel):
    heading: str
    content: dict[str, Any] | list[Any] | None = None
    created_by_type: FindingCreatedByType = "user"
    status: FindingStatus = "draft"
    part_ids: list[int] = Field(default_factory=list)
    source_ids: list[int] = Field(default_factory=list)


class FindingUpdate(BaseModel):
    heading: str | None = None
    content: dict[str, Any] | list[Any] | None = None
    created_by_type: FindingCreatedByType | None = None
    status: FindingStatus | None = None
    part_ids: list[int] | None = None
    source_ids: list[int] | None = None


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    heading: str
    content: dict[str, Any] | list[Any] | None
    created_by_type: FindingCreatedByType
    status: FindingStatus
    part_ids: list[int]
    source_ids: list[int]
    created_at: datetime
    updated_at: datetime
