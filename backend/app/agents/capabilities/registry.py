
from dataclasses import dataclass
from typing import Literal


Action = Literal[
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

TargetType = Literal[
    "project",
    "part",
    "source",
    "finding",
    "asset",
    "script_draft",
    "script",
    "part_relationship",
]


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    action: Action
    target_types: tuple[TargetType, ...]
    description: str
    executor_ready: bool = False
    requires_approval: bool = True


CAPABILITIES: dict[str, CapabilitySpec] = {
    "research": CapabilitySpec(
        name="research",
        action="research",
        target_types=("project", "part"),
        description="Research a project or Part and return evidence and source candidates.",
    ),
    "evaluate_findings": CapabilitySpec(
        name="evaluate_findings",
        action="evaluate",
        target_types=("finding",),
        description="Evaluate findings for relevance, evidence, and conflicts.",
    ),
    "create_part": CapabilitySpec(
        name="create_part",
        action="create",
        target_types=("part",),
        description="Create a Part inside the current project.",
    ),
    "update_part": CapabilitySpec(
        name="update_part",
        action="update",
        target_types=("part",),
        description="Update an existing Part.",
    ),
    "delete_part": CapabilitySpec(
        name="delete_part",
        action="delete",
        target_types=("part",),
        description="Delete a Part after explicit user approval.",
    ),
    "create_source": CapabilitySpec(
        name="create_source",
        action="create",
        target_types=("source",),
        description="Save a source and optionally associate it with Parts.",
    ),
    "update_source": CapabilitySpec(
        name="update_source",
        action="update",
        target_types=("source",),
        description="Update a source and its Part associations.",
    ),
    "delete_source": CapabilitySpec(
        name="delete_source",
        action="delete",
        target_types=("source",),
        description="Delete a source after explicit user approval.",
    ),
    "create_finding": CapabilitySpec(
        name="create_finding",
        action="create",
        target_types=("finding",),
        description="Save a finding with optional Part and Source associations.",
    ),
    "update_finding": CapabilitySpec(
        name="update_finding",
        action="update",
        target_types=("finding",),
        description="Update a finding and its associations.",
    ),
    "delete_finding": CapabilitySpec(
        name="delete_finding",
        action="delete",
        target_types=("finding",),
        description="Delete a finding after explicit user approval.",
    ),
    "generate_script_draft": CapabilitySpec(
        name="generate_script_draft",
        action="generate_draft",
        target_types=("script_draft",),
        description="Generate and save an unaccepted script draft.",
    ),
    "update_script_draft": CapabilitySpec(
        name="update_script_draft",
        action="update",
        target_types=("script_draft",),
        description="Update an existing script draft.",
    ),
    "accept_script_draft": CapabilitySpec(
        name="accept_script_draft",
        action="accept",
        target_types=("script_draft",),
        description="Accept a draft and create a new ScriptRevision.",
    ),
    "restore_script_revision": CapabilitySpec(
        name="restore_script_revision",
        action="restore",
        target_types=("script",),
        description="Restore an old revision by creating a new revision.",
    ),
    "create_part_commit": CapabilitySpec(
        name="create_part_commit",
        action="commit",
        target_types=("part",),
        description="Create a Part history snapshot.",
    ),
    "restore_part_revision": CapabilitySpec(
        name="restore_part_revision",
        action="restore",
        target_types=("part",),
        description="Restore a Part revision non-destructively.",
    ),
    "request_user_review": CapabilitySpec(
        name="request_user_review",
        action="request_review",
        target_types=("script_draft",),
        description="Present an existing draft for user review.",
    ),
}


def get_capability(name: str) -> CapabilitySpec:
    try:
        return CAPABILITIES[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported capability: {name}") from exc


def validate_task_capability(task) -> CapabilitySpec:
    """Validate a proposed task against its registered capability."""
    spec = get_capability(task.capability)

    if task.action != spec.action:
        raise ValueError(
            f"Capability '{spec.name}' requires action '{spec.action}', "
            f"not '{task.action}'."
        )

    if task.target_type not in spec.target_types:
        raise ValueError(
            f"Capability '{spec.name}' requires one of target types "
            f"{spec.target_types}, not '{task.target_type}'."
        )

    return spec
