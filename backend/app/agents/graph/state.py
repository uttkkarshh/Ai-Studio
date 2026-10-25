
from typing import Any, TypedDict

from app.agents.completion_agent.schemas import TaskResult
from app.agents.orchestrator.schemas import OrchestratorAction
from app.agents.work_planner.schemas import WorkPlan
from app.context.schemas import PlannerContext


class AgentState(TypedDict):
    project_id: int
    scope: str
    part_id: int | None
    user_message: str
    user_objective: str | None
    current_proposal: Any | None
    context: PlannerContext | None
    action: OrchestratorAction | None
    plan: WorkPlan | None
    message: str | None
    requires_approval: bool
    proposal: dict[str, Any] | None


class CompletionState(TypedDict):
    project_id: int
    scope: str
    part_id: int | None
    user_request: str
    accepted_plan: WorkPlan
    task_results: list[TaskResult]
    status: str
