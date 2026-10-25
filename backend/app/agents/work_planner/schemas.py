
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WorkTask(BaseModel):
    task_id: str = Field(
        description="Unique identifier within this plan."
    )
    title: str = Field(
        description="Short task title for the UI."
    )
    action: Literal[
        "research",
        "evaluate",
        "create",
        "update",
        "delete",
        "generate_draft",
        "accept",
        "restore",
        "commit",
        "request_review",
    ]
    capability: str = Field(
        description="Name of a registered application capability."
    )
    target_type: Literal[
        "project",
        "part",
        "source",
        "finding",
        "asset",
        "script_draft",
        "script",
        "part_relationship",
    ]
    target_id: int | None = Field(
        default=None,
        description="Existing target ID, if applicable."
    )
    intent: str = Field(
        description="What the executor should accomplish."
    )
    expected_output: str
    completion_criteria: list[str] = Field(min_length=1)


class WorkPlan(BaseModel):
    objective: str
    rationale: str
    tasks: list[WorkTask] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_unique_task_ids(self):
        task_ids = [task.task_id for task in self.tasks]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task IDs must be unique within a plan.")

        return self
