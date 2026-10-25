from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    objective: str | None = None
    initial_input: str | None = None
    initial_script: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        if value is None:
            raise ValueError("name is required")

        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("objective", "initial_input", mode="before")
    @classmethod
    def strip_optional_project_text(cls, value):
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("description", "initial_script", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    objective: str | None = None
    initial_input: str | None = None
    initial_script: str | None = None

    @field_validator("name", "objective", "initial_input", mode="before")
    @classmethod
    def strip_if_present(cls, value, info):
        if value is None:
            return None

        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError(f"{info.field_name} cannot be blank")
        return cleaned

    @field_validator("description", "initial_script", mode="before")
    @classmethod
    def strip_optional_update_text(cls, value):
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None


class ProjectAIMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    scope: str = "project"
    part_id: int | None = None
    current_proposal: dict | None = None

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value):
        if value is None:
            raise ValueError("message is required")

        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("message is required")
        return cleaned

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value):
        normalized = str(value).strip().lower()
        if normalized not in {"project", "part"}:
            raise ValueError("scope must be 'project' or 'part'")
        return normalized

    @field_validator("part_id")
    @classmethod
    def validate_part_id(cls, value, info):
        if info.data.get("scope") == "part" and value is None:
            raise ValueError("part_id is required when scope is 'part'")
        return value


class ProjectAIActionResponse(BaseModel):
    action: str
    reason: str


class ProjectAIResponse(BaseModel):
    action: ProjectAIActionResponse
    message: str
    requires_approval: bool = False
    proposal: dict | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    objective: str | None
    initial_input: str | None
    initial_script: str | None
    created_at: datetime
    updated_at: datetime
