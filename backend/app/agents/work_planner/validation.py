
from app.agents.capabilities.registry import validate_task_capability
from app.agents.work_planner.schemas import WorkPlan


def validate_work_plan(plan: WorkPlan) -> WorkPlan:
    for task in plan.tasks:
        validate_task_capability(task)

    return plan
