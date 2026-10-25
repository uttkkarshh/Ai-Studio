
import json
import logging
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.completion_agent.completer import CompletionAgent
from app.agents.completion_agent.execution import (
    execute_accepted_plan,
    validate_accepted_plan,
)
from app.agents.graph.state import AgentState, CompletionState
from app.agents.orchestrator.orchestrator import Orchestrator
from app.agents.orchestrator.schemas import OrchestratorAction
from app.agents.work_planner.planner import WorkPlanner
from app.agents.work_planner.model_factory import create_work_planner_model
from app.agents.work_planner.schemas import WorkPlan
from app.context.service import ContextService
from app.db.database import SessionLocal


logger = logging.getLogger(__name__)


def _coerce_current_plan(value: Any | None) -> WorkPlan | None:
    """Read only the new WorkPlan format; never coerce a legacy ProjectPlan."""
    if isinstance(value, WorkPlan):
        return value

    if not isinstance(value, dict):
        return None

    if value.get("type") == "work_plan":
        value = value.get("data")

    if not isinstance(value, dict):
        return None

    try:
        return WorkPlan.model_validate(value)
    except ValidationError as error:
        logger.warning(
            "Current WorkPlan could not be parsed validation_errors=%s",
            error.errors(include_input=False),
        )
        return None


def _load_context_for_state(state: AgentState):
    started_at = perf_counter()
    project_id = state["project_id"]
    scope = state.get("scope", "project")
    logger.info(
        "graph context load started project_id=%s scope=%s",
        project_id,
        scope,
    )
    db = SessionLocal()
    try:
        context_service = ContextService(db)

        if scope == "part":
            context = context_service.get_part_context(
                project_id=project_id,
                part_id=state["part_id"],
            )
        else:
            context = context_service.get_project_context(project_id=project_id)
        logger.info(
            "graph context load completed project_id=%s scope=%s part_count=%s duration_ms=%.2f",
            project_id,
            scope,
            len(context.current_parts),
            (perf_counter() - started_at) * 1000,
        )
        return context
    finally:
        db.close()


def _as_dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()

    if isinstance(value, dict):
        return value

    return {}


def orchestrator_node(state: AgentState):
    logger.info(
        "graph node entered node=orchestrator project_id=%s scope=%s",
        state["project_id"],
        state.get("scope", "project"),
    )
    orchestrator = Orchestrator()

    user_message = (
        state.get("user_message")
        or state.get("user_objective")
        or ""
    ).strip()

    current_plan = (
        _coerce_current_plan(state.get("plan"))
        or _coerce_current_plan(state.get("current_proposal"))
    )

    context = state.get("context") or _load_context_for_state(state)

    decision_started_at = perf_counter()
    action = orchestrator.decide(
        user_message=user_message,
        current_plan=current_plan,
        current_proposal=state.get("current_proposal"),
        scope=state.get("scope", "project"),
        part_id=state.get("part_id"),
        context=context,
    )
    logger.info(
        "orchestrator action selected project_id=%s scope=%s action=%s duration_ms=%.2f",
        state["project_id"],
        state.get("scope", "project"),
        action.action,
        (perf_counter() - decision_started_at) * 1000,
    )

    result = {
        "action": action,
        "context": context,
        "message": None,
        "requires_approval": False,
        "proposal": None,
    }

    if action.action in ("create_plan", "revise_plan"):
        result["message"] = (
            "Preparing a new work plan."
            if action.action == "create_plan"
            else "Preparing a revision of the current work plan."
        )

    elif action.action == "research":
        result["message"] = (
            "Research execution is not connected to this workflow yet. "
            "No research has been performed."
        )

    elif action.action == "generate_script":
        result["message"] = (
            "Script generation is not connected to this workflow yet. "
            "No script has been generated."
        )

    elif action.action == "request_approval":
        result["message"] = (
            "Approval is required before proceeding. "
            "No tasks have been executed."
        )
        result["requires_approval"] = True

    elif action.action == "answer":
        result["message"] = action.reason

    elif action.action == "finish":
        result["message"] = action.reason

    return result


def plan_work_node(state: AgentState):
    logger.info(
        "graph node entered node=plan_work project_id=%s scope=%s",
        state["project_id"],
        state.get("scope", "project"),
    )
    context = state.get("context") or _load_context_for_state(state)

    action = state.get("action")
    revision_feedback = (
        state.get("user_message")
        or state.get("user_objective")
        or ""
    ).strip()
    user_message = revision_feedback

    if isinstance(action, OrchestratorAction) and action.objective:
        user_message = action.objective

    current_plan = (
        _coerce_current_plan(state.get("plan"))
        or _coerce_current_plan(state.get("current_proposal"))
    )

    # Include the existing plan when revising so the Planner can use it.
    planner_context = {
        "project_context": _as_dict(context),
        "existing_work_plan": (
            current_plan.model_dump() if current_plan else None
        ),
        "request_type": (
            action.action
            if isinstance(action, OrchestratorAction)
            else "create_plan"
        ),
        "revision_feedback": (
            revision_feedback
            if isinstance(action, OrchestratorAction)
            and action.action == "revise_plan"
            else None
        ),
    }

    planner = WorkPlanner(create_work_planner_model())
    plan = planner.plan(
        objective=user_message,
        context=json.dumps(
            planner_context,
            ensure_ascii=False,
            default=str,
        ),
    )
    logger.info(
        "graph WorkPlanner result ready project_id=%s task_count=%s",
        state["project_id"],
        len(plan.tasks),
    )

    proposal = {
        "type": "work_plan",
        "data": plan.model_dump(),
    }

    return {
        "context": context,
        "plan": plan,
        "message": (
            "I prepared a revised work plan for your review."
            if isinstance(action, OrchestratorAction)
            and action.action == "revise_plan"
            else "I prepared a work plan for your review."
        ),
        "requires_approval": True,
        "proposal": proposal,
    }


def route_after_orchestrator(state: AgentState):
    action = state.get("action")

    if action is None:
        raise ValueError("Orchestrator did not produce an action")

    if isinstance(action, OrchestratorAction):
        action_name = action.action
    elif isinstance(action, dict):
        action_name = action.get("action")
    else:
        raise ValueError("Orchestrator returned an unsupported action format")

    routes = {
        "create_plan": "plan_work",
        "revise_plan": "plan_work",
        "research": END,
        "generate_script": END,
        "request_approval": END,
        "answer": END,
        "finish": END,
    }

    if action_name not in routes:
        raise ValueError(f"Unsupported Orchestrator action: {action_name}")

    selected_route = routes[action_name]
    logger.info(
        "graph route selected action=%s route=%s",
        action_name,
        "END" if selected_route == END else selected_route,
    )
    return selected_route


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("plan_work", plan_work_node)

    graph.add_edge(START, "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "plan_work": "plan_work",
            END: END,
        },
    )

    graph.add_edge("plan_work", END)

    return graph.compile()


def completion_node(state: CompletionState, db: Session, completion_agent: CompletionAgent):
    plan = WorkPlan.model_validate(state["accepted_plan"])
    validate_accepted_plan(
        db=db,
        project_id=state["project_id"],
        plan=plan,
        scope=state["scope"],
        part_id=state.get("part_id"),
    )
    task_results = execute_accepted_plan(
        db=db,
        project_id=state["project_id"],
        plan=plan,
        scope=state["scope"],
        part_id=state.get("part_id"),
        user_request=state.get("user_request") or plan.objective,
        completion_agent=completion_agent,
    )
    if all(result.status == "draft_ready" for result in task_results):
        overall_status = "drafts_ready"
    elif any(result.status == "failed" for result in task_results):
        overall_status = "failed"
    else:
        overall_status = "needs_attention"
    return {"task_results": task_results, "status": overall_status}


def build_completion_graph(
    db: Session,
    completion_agent: CompletionAgent | None = None,
):
    agent = completion_agent or CompletionAgent()
    graph = StateGraph(CompletionState)
    graph.add_node(
        "complete_accepted_plan",
        lambda state: completion_node(state, db, agent),
    )
    graph.add_edge(START, "complete_accepted_plan")
    graph.add_edge("complete_accepted_plan", END)
    return graph.compile()
