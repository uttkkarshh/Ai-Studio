import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.capabilities.registry import validate_task_capability
from app.agents.completion_agent.completer import CompletionAgent
from app.agents.completion_agent.schemas import (
    CompletionTaskInput,
    DraftValidation,
    FindingTaskResult,
    PartTaskResult,
    ScriptContext,
    ScriptDraftTaskResult,
    SourceContext,
    SourceTaskResult,
    TaskResult,
)
from app.agents.work_planner.schemas import WorkPlan, WorkTask
from app.context.service import ContextService
from app.models import Part, Project, ScriptDraft, Source


logger = logging.getLogger(__name__)

SUPPORTED_CREATE_TASKS = {
    "create_part": ("create", "part"),
    "create_finding": ("create", "finding"),
    "create_source": ("create", "source"),
    "generate_script_draft": ("generate_draft", "script_draft"),
}


def validate_accepted_plan(
    db: Session,
    project_id: int,
    plan: WorkPlan,
    scope: str,
    part_id: int | None,
) -> None:
    if db.get(Project, project_id) is None:
        raise ValueError(f"Project {project_id} not found")
    if scope not in {"project", "part"}:
        raise ValueError("scope must be 'project' or 'part'")
    if scope == "part" and part_id is None:
        raise ValueError("part_id is required when scope is 'part'")
    if scope == "project" and part_id is not None:
        raise ValueError("part_id can only be provided when scope is 'part'")
    if part_id is not None:
        part = db.scalar(
            select(Part).where(Part.id == part_id, Part.project_id == project_id)
        )
        if part is None:
            raise ValueError("Part not found for this project")

    for task in plan.tasks:
        validate_task_capability(task)

        if task.capability not in SUPPORTED_CREATE_TASKS:
            raise ValueError(
                f"Capability '{task.capability}' is not supported for draft generation."
            )
        expected_action, expected_target = SUPPORTED_CREATE_TASKS[task.capability]
        if (task.action, task.target_type) != (expected_action, expected_target):
            raise ValueError(
                f"Capability '{task.capability}' only supports "
                f"action '{expected_action}' and target '{expected_target}'."
            )
        if task.target_id is not None:
            raise ValueError(
                f"Create task '{task.task_id}' must not include target_id."
            )


def _task_result(task: WorkTask, **values: Any) -> TaskResult:
    result_types = {
        "part": PartTaskResult,
        "finding": FindingTaskResult,
        "source": SourceTaskResult,
        "script_draft": ScriptDraftTaskResult,
    }
    result_type = result_types.get(task.target_type)
    if result_type is None:
        raise ValueError(f"Unsupported draft target: {task.target_type}")
    return result_type(
        task_id=task.task_id,
        target_type=task.target_type,
        target_id=None,
        requires_user_approval=True,
        **values,
    )


def _get_completion_context(
    db: Session,
    project_id: int,
    scope: str,
    part_id: int | None,
    task: WorkTask,
    user_request: str,
) -> CompletionTaskInput:
    context_service = ContextService(db)
    project_context = (
        context_service.get_part_context(project_id, part_id)
        if scope == "part" and part_id is not None
        else context_service.get_project_context(project_id)
    )

    source_query = select(Source).where(Source.project_id == project_id)
    if part_id is not None:
        source_query = source_query.where(Source.parts.any(Part.id == part_id))
    sources = db.scalars(source_query.order_by(Source.id)).all()
    source_context = [
        SourceContext(
            id=source.id,
            title=source.title,
            url=source.url,
            source_type=source.source_type,
            content=source.content if part_id is not None else None,
            metadata=source.metadata_,
        )
        for source in sources
    ]

    script_context = None
    if task.target_type == "script_draft" and part_id is not None:
        draft = db.scalar(
            select(ScriptDraft)
            .where(ScriptDraft.part_id == part_id)
            .order_by(ScriptDraft.created_at.desc(), ScriptDraft.id.desc())
            .limit(1)
        )
        selected_part = db.scalar(
            select(Part).where(Part.id == part_id, Part.project_id == project_id)
        )
        if draft is not None:
            script_context = ScriptContext(
                title=draft.title,
                content=draft.content,
                created_by_type=draft.created_by_type,
                status=draft.status,
            )
        elif selected_part is not None and selected_part.script is not None:
            revision = selected_part.script.current_revision
            if revision is not None:
                script_context = ScriptContext(
                    title=None,
                    content=revision.content,
                    created_by_type=revision.created_by_type,
                    status="current_revision",
                )

    target_instructions = {
        "part": (
            "Return only PartCreate fields: title, objective, description, "
            "status, and position. Do not include project_id or generated IDs."
        ),
        "finding": (
            "Return only FindingCreate fields: heading, content, created_by_type, "
            "status, part_ids, and source_ids. Relationship IDs must be from the "
            "supplied project context."
        ),
        "source": (
            "Return only SourceCreate fields: title, url, source_type, content, "
            "metadata, and part_ids. Do not claim source content was retrieved "
            "unless it appears in the supplied context."
        ),
        "script_draft": (
            "Return only ScriptDraftCreate fields: title, content, and "
            "created_by_type. content must be a JSON object or array, never "
            "plain text; prefer {\"sections\": [{\"type\": \"narration\", "
            "\"content\": \"...\"}]}. This draft is for the selected Part."
        ),
    }[task.target_type]

    return CompletionTaskInput(
        project_id=project_id,
        scope=scope,
        part_id=part_id,
        user_request=user_request,
        task=task,
        project_context=project_context,
        sources=source_context,
        script_context=script_context,
        existing_target=None,
        target_instructions=target_instructions,
    )


def _validate_draft_relationships(
    db: Session,
    project_id: int,
    draft: Any,
    allowed_part_ids: set[int],
    allowed_source_ids: set[int],
) -> None:
    part_ids = getattr(draft, "part_ids", [])
    source_ids = getattr(draft, "source_ids", [])
    if not set(part_ids).issubset(allowed_part_ids):
        raise ValueError("Draft refers to a Part that was not supplied in context.")
    if not set(source_ids).issubset(allowed_source_ids):
        raise ValueError("Draft refers to a Source that was not supplied in context.")
    if part_ids:
        valid_part_ids = set(
            db.scalars(
                select(Part.id).where(
                    Part.project_id == project_id,
                    Part.id.in_(set(part_ids)),
                )
            ).all()
        )
        if valid_part_ids != set(part_ids):
            raise ValueError("Draft refers to a Part outside this project.")
    if source_ids:
        valid_source_ids = set(
            db.scalars(
                select(Source.id).where(
                    Source.project_id == project_id,
                    Source.id.in_(set(source_ids)),
                )
            ).all()
        )
        if valid_source_ids != set(source_ids):
            raise ValueError("Draft refers to a Source outside this project.")


def execute_accepted_plan(
    db: Session,
    project_id: int,
    plan: WorkPlan,
    scope: str,
    part_id: int | None,
    user_request: str,
    completion_agent: CompletionAgent,
) -> list[TaskResult]:
    results: list[TaskResult] = []

    for task in plan.tasks:
        if task.target_type == "script_draft" and part_id is None:
            results.append(
                _task_result(
                    task,
                    status="needs_clarification",
                    draft=None,
                    validation=DraftValidation(
                        schema_valid=True,
                        warnings=["A Part must be selected to generate a script draft."],
                    ),
                    clarification_questions=[
                        "Which Part should this script draft be created for?"
                    ],
                )
            )
            continue

        try:
            task_input = _get_completion_context(
                db,
                project_id,
                scope,
                part_id,
                task,
                user_request,
            )
            generated = completion_agent.complete(task_input)
            if generated.status == "needs_clarification":
                if generated.draft is not None or not generated.clarification_questions:
                    raise ValueError(
                        "Clarification results must omit the draft and include questions."
                    )
                results.append(
                    _task_result(
                        task,
                        status="needs_clarification",
                        draft=None,
                        validation=generated.validation,
                        clarification_questions=generated.clarification_questions,
                    )
                )
                continue

            if generated.draft is None:
                raise ValueError("Draft-ready output did not include a draft.")
            _validate_draft_relationships(
                db,
                project_id,
                generated.draft,
                allowed_part_ids={
                    part.id for part in task_input.project_context.current_parts
                },
                allowed_source_ids={source.id for source in task_input.sources},
            )
            results.append(
                _task_result(
                    task,
                    status="draft_ready",
                    draft=generated.draft,
                    validation=DraftValidation(
                        schema_valid=True,
                        warnings=generated.validation.warnings,
                    ),
                )
            )
        except (ValidationError, ValueError) as error:
            error_details = (
                error.errors(include_input=False)
                if isinstance(error, ValidationError)
                else str(error)
            )
            logger.warning(
                "Completion task failed task_id=%s error=%s",
                task.task_id,
                error_details,
            )
            results.append(
                _task_result(
                    task,
                    status="failed",
                    draft=None,
                    validation=DraftValidation(
                        schema_valid=False,
                        warnings=[],
                    ),
                    error="The generated draft could not be validated.",
                )
            )
        except Exception:
            logger.exception(
                "Completion task generation failed task_id=%s",
                task.task_id,
            )
            results.append(
                _task_result(
                    task,
                    status="failed",
                    draft=None,
                    validation=DraftValidation(
                        schema_valid=False,
                        warnings=[],
                    ),
                    error="Draft generation failed.",
                )
            )

    return results
