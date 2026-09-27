from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScriptDraftCreate(BaseModel):
    title: str | None = None
    content: dict[str, Any] | list[Any] | None = None
    created_by_type: str = Field(default="user")


class ScriptDraftUpdate(BaseModel):
    title: str | None = None
    content: dict[str, Any] | list[Any] | None = None
    created_by_type: str | None = None
    status: str | None = None


class ScriptDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    title: str | None
    content: dict[str, Any] | list[Any] | None
    created_by_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class ScriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    current_revision_id: int | None
    created_at: datetime
    updated_at: datetime


class ScriptRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    script_id: int
    revision_number: int
    content: dict[str, Any] | list[Any] | None
    created_by_type: str
    commit_message: str
    created_at: datetime
    source_draft_id: int | None


class ScriptAcceptanceResponse(ScriptRevisionResponse):
    status: str


class ScriptRevisionDetailResponse(ScriptRevisionResponse):
    pass
