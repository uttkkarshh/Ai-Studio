from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agents.work_planner.schemas import WorkPlan, WorkTask
from app.context.schemas import PlannerContext
from app.schemas import FindingCreate, PartCreate, ScriptDraftCreate, SourceCreate


CompletionStatus = Literal["draft_ready", "needs_clarification", "failed"]
TaskResultStatus = CompletionStatus


class SourceContext(BaseModel):
    id: int
    title: str
    url: str | None
    source_type: str
    content: str | None = None
    metadata: dict[str, Any] | None = None


class ScriptContext(BaseModel):
    title: str | None
    content: dict[str, Any] | list[Any] | None
    created_by_type: str
    status: str


class PartDraftPayload(PartCreate):
    model_config = ConfigDict(extra="forbid")


class FindingDraftPayload(FindingCreate):
    model_config = ConfigDict(extra="forbid")


class SourceDraftPayload(SourceCreate):
    model_config = ConfigDict(extra="forbid")


class ScriptDraftPayload(ScriptDraftCreate):
    model_config = ConfigDict(extra="forbid")


class CompletionTaskInput(BaseModel):
    project_id: int
    scope: Literal["project", "part"]
    part_id: int | None = None
    user_request: str
    task: WorkTask
    project_context: PlannerContext
    sources: list[SourceContext] = Field(default_factory=list)
    script_context: ScriptContext | None = None
    existing_target: dict[str, Any] | None = None
    target_instructions: str


class DraftValidation(BaseModel):
    schema_valid: bool
    warnings: list[str] = Field(default_factory=list)


class CompletionGenerationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["draft_ready", "needs_clarification"]
    validation: DraftValidation = Field(
        default_factory=lambda: DraftValidation(schema_valid=True)
    )
    clarification_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_generation_status(self):
        draft = getattr(self, "draft", None)
        if self.status == "draft_ready" and draft is None:
            raise ValueError("draft_ready output must include a draft")
        if self.status == "needs_clarification":
            if draft is not None:
                raise ValueError("needs_clarification output must not include a draft")
            if not self.clarification_questions:
                raise ValueError(
                    "needs_clarification output must include clarification questions"
                )
        return self


class PartCompletionGeneration(CompletionGenerationBase):
    draft: PartDraftPayload | None = None


class FindingCompletionGeneration(CompletionGenerationBase):
    draft: FindingDraftPayload | None = None


class SourceCompletionGeneration(CompletionGenerationBase):
    draft: SourceDraftPayload | None = None


class ScriptDraftCompletionGeneration(CompletionGenerationBase):
    draft: ScriptDraftPayload | None = None


class TaskResultBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: TaskResultStatus
    target_id: int | None = None
    validation: DraftValidation
    requires_user_approval: bool = True
    clarification_questions: list[str] = Field(default_factory=list)
    error: str | None = None


class PartTaskResult(TaskResultBase):
    target_type: Literal["part"]
    draft: PartDraftPayload | None = None


class FindingTaskResult(TaskResultBase):
    target_type: Literal["finding"]
    draft: FindingDraftPayload | None = None


class SourceTaskResult(TaskResultBase):
    target_type: Literal["source"]
    draft: SourceDraftPayload | None = None


class ScriptDraftTaskResult(TaskResultBase):
    target_type: Literal["script_draft"]
    draft: ScriptDraftPayload | None = None


TaskResult = Annotated[
    Union[
        PartTaskResult,
        FindingTaskResult,
        SourceTaskResult,
        ScriptDraftTaskResult,
    ],
    Field(discriminator="target_type"),
]


class PlanExecutionRequest(BaseModel):
    plan: WorkPlan
    scope: Literal["project", "part"] = "project"
    part_id: int | None = None
    user_request: str | None = None

    @model_validator(mode="after")
    def validate_scope_part(self):
        if self.scope == "part" and self.part_id is None:
            raise ValueError("part_id is required when scope is 'part'")
        if self.scope == "project" and self.part_id is not None:
            raise ValueError("part_id can only be provided when scope is 'part'")
        return self

    @field_validator("user_request", mode="before")
    @classmethod
    def clean_user_request(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class PlanExecutionResponse(BaseModel):
    project_id: int
    status: Literal["drafts_ready", "needs_attention", "failed"]
    objective: str
    tasks: list[TaskResult]
