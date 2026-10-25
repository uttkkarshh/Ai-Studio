import json
import logging
from time import perf_counter

from app.agents.capabilities.registry import CAPABILITIES
from app.agents.work_planner.schemas import WorkPlan
from app.agents.work_planner.validation import validate_work_plan


logger = logging.getLogger(__name__)


def _project_structure_guidance(context: str) -> str:
    try:
        context_data = json.loads(context) if isinstance(context, str) else context
    except json.JSONDecodeError as error:
        logger.warning("WorkPlanner context JSON could not be parsed: %s", error)
        return ""

    if not isinstance(context_data, dict):
        return ""

    project_context = context_data.get("project_context", context_data)
    if not isinstance(project_context, dict):
        return ""

    selected_part = project_context.get("selected_part")
    if isinstance(selected_part, dict):
        return (
            "This request is scoped to the selected Part. Focus tasks on that "
            "Part and do not propose create_part tasks or recreate project structure."
        )

    current_parts = project_context.get("current_parts")
    if not isinstance(current_parts, list):
        return ""

    existing_plan = context_data.get("existing_work_plan")
    already_planned_part_creation = (
        isinstance(existing_plan, dict)
        and isinstance(existing_plan.get("tasks"), list)
        and any(
            isinstance(task, dict) and task.get("capability") == "create_part"
            for task in existing_plan["tasks"]
        )
    )

    if not current_parts:
        if already_planned_part_creation:
            return (
                "The project currently has no persisted Parts, but the existing "
                "WorkPlan already proposes Part creation. Revise those tasks "
                "instead of adding duplicate create_part tasks unless the user "
                "explicitly asks for additional Parts."
            )
        return (
            "The project currently has no Parts. For an initial project plan, "
            "normally include one or more tailored create_part tasks that organize "
            "the user's objective. Choose the Part topics from this objective; "
            "do not use a fixed template. Keep the entire plan within five "
            "independent tasks."
        )

    return (
        "The project already has Parts. Review their titles and objectives in "
        "the supplied context and do not propose duplicate create_part tasks "
        "for work those Parts already cover. Add a Part only if the objective "
        "clearly needs a distinct, currently missing area."
    )


class WorkPlanner:
    def __init__(self, planner_model):
        self.planner_model = planner_model

    def plan(self, objective: str, context: str = "") -> WorkPlan:
        logger.info("WorkPlanner invocation started")
        capability_descriptions = "\n".join(
            f"- {spec.name}: action={spec.action}, "
            f"target_types={spec.target_types}, "
            f"description={spec.description}"
            for spec in CAPABILITIES.values()
        )
        structure_guidance = _project_structure_guidance(context)

        system_prompt = f"""
You are the Planner in an auditable AI workflow.

Return the result as valid JSON matching the required WorkPlan structure.

Propose 1 to 5 independent tasks for the user's objective.
Tasks must not have dependencies or nested tasks.

You propose tasks only. Never execute them or claim they are completed.

Allowed actions:
research, evaluate, create, update, delete, generate_draft,
accept, restore, commit, request_review.

Allowed target types:
project, part, source, finding, asset, script_draft, script,
part_relationship.

Each task must have a unique task_id, title, action, capability,
target_type, intent, expected_output, and completion_criteria.

Do not invent database IDs. Use null when a target ID is unknown
or not applicable.

Propose only tasks relevant to the user's objective.
{structure_guidance}

Your output must include every required WorkPlan field:
- objective
- rationale
- tasks

For every task:
- completion_criteria MUST be a JSON array of strings.
- capability MUST exactly match a registered capability name.
- The action and target_type MUST match that capability.
- Never invent capability names.
- If no registered capability supports a task, do not propose it.

Registered capabilities — use ONLY these:
{capability_descriptions}

The capability name, action, and target_type in every task
must match one of these registered entries exactly.
"""

        messages = [
            ("system", system_prompt),
            (
                "human",
                f"Objective:\n{objective}\n\nContext:\n{context}",
            ),
        ]

        model_started_at = perf_counter()
        plan = self.planner_model.invoke(messages)
        logger.info(
            "WorkPlanner model invocation completed duration_ms=%.2f",
            (perf_counter() - model_started_at) * 1000,
        )

        validation_started_at = perf_counter()
        validated_plan = validate_work_plan(plan)

        logger.info(
            "WorkPlanner capability validation succeeded task_count=%s duration_ms=%.2f",
            len(validated_plan.tasks),
            (perf_counter() - validation_started_at) * 1000,
        )
        logger.info(
            "WorkPlanner invocation completed task_count=%s",
            len(validated_plan.tasks),
        )
        return validated_plan
