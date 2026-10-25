
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class WorkStepProposal(BaseModel):
    """A proposed unit of work. It does not execute anything."""

    step_key: str = Field(
        description="Unique, stable key within this plan, such as research_topic."
    )
    title: str = Field(description="Short title displayed in the UI.")
    description: str = Field(
        description="Detailed instructions the executor should follow."
    )

    operation: Literal[
    "research",
    "evaluate",
    "create",
    "modify",
    "delete",
    "generate_draft",
    "accept",
    "restore",
    "commit",
    "request_review",
]

    object_type: Literal[
        "project",
        "part",
        "source",
        "finding",
        "asset",
        "script_draft",
        "script",
        "part_relationship",
    ]

    target_scope: Literal["project", "part"]
    target_part_id: int | None = None
    target_entity_id: int | None = None

    capability: Literal[
        "research",
        "evaluate_findings",
        "create_part",
        "update_part",
        "create_source",
        "update_source",
        "create_finding",
        "update_finding",
        "generate_script_draft",
        "update_script_draft",
        "accept_script_draft",
        "restore_script_revision",
        "create_part_commit",
        "restore_part_revision",
        "request_user_review",
        "delete_part",
        "delete_source",
        "delete_finding",
    ] = Field(
        description="Registered capability that can execute this step."
    )

    depends_on: list[str] = Field(
        default_factory=list,
        description="Step keys that must complete before this step can execute.",
    )
    inputs: dict = Field(
        default_factory=dict,
        description="Structured parameters and references required for execution.",
    )
    expected_output: str = Field(
        description="The concrete result expected from this step."
    )
    completion_criteria: list[str] = Field(
        min_length=1,
        description="Conditions that must be satisfied before marking complete.",
    )


class WorkPlan(BaseModel):
    """A proposed, ordered workflow for a project or a specific Part."""

    objective: str
    rationale: str = Field(
        description="Brief explanation of why this sequence of steps is appropriate."
    )
    steps: list[WorkStepProposal] = Field(
        min_length=1,
        max_length=5,
        description="Ordered steps proposed for user review and approval.",
    )

    @model_validator(mode="after")
    def validate_dependencies(self):
        keys = [step.step_key for step in self.steps]

        if len(keys) != len(set(keys)):
            raise ValueError("WorkStep keys must be unique.")

        seen = set()
        for step in self.steps:
            if step.step_key in step.depends_on:
                raise ValueError("A WorkStep cannot depend on itself.")

            unknown = set(step.depends_on) - set(keys)
            if unknown:
                raise ValueError(
                    f"WorkStep {step.step_key} has unknown dependencies: "
                    f"{sorted(unknown)}"
                )

            if not set(step.depends_on).issubset(seen):
                raise ValueError(
                    f"Dependencies for {step.step_key} must appear earlier "
                    "in the proposed plan."
                )

            seen.add(step.step_key)

        return self
