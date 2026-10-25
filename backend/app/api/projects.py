import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.completion_agent.execution import validate_accepted_plan
from app.agents.completion_agent.schemas import (
    PlanExecutionRequest,
    PlanExecutionResponse,
)
from app.agents.graph.graph import build_completion_graph, build_graph
from app.db.dependencies import get_db
from app.models import Part, Project
from app.schemas import (
    ProjectAIMessageRequest,
    ProjectAIResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    new_project = Project(**project.model_dump())
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


@router.get("/", response_model=list[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.id)).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/ai/message", response_model=ProjectAIResponse)
def project_ai_message(project_id: int, payload: ProjectAIMessageRequest, db: Session = Depends(get_db)):
    logger.info(
        "AI workflow request started project_id=%s scope=%s",
        project_id,
        payload.scope,
    )
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.scope == "part":
        if payload.part_id is None:
            raise HTTPException(status_code=422, detail="part_id is required when scope is 'part'")

        part = db.get(Part, payload.part_id)
        if part is None or part.project_id != project_id:
            raise HTTPException(status_code=404, detail="Part not found for this project")

    graph = build_graph()
    graph_started_at = perf_counter()
    try:
        graph_result = graph.invoke(
            {
                "project_id": project_id,
                "scope": payload.scope,
                "part_id": payload.part_id,
                "user_message": payload.message,
                "user_objective": payload.message,
                "current_proposal": payload.current_proposal,
                "context": None,
                "action": None,
                "plan": None,
                "message": None,
                "requires_approval": False,
                "proposal": None,
            }
        )
    except Exception as error:
        graph_duration_ms = (perf_counter() - graph_started_at) * 1000
        logger.exception(
            "AI workflow graph failed project_id=%s scope=%s duration_ms=%.2f",
            project_id,
            payload.scope,
            graph_duration_ms,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI workflow request failed.",
        ) from error

    graph_duration_ms = (perf_counter() - graph_started_at) * 1000
    logger.info(
        "AI workflow graph completed project_id=%s scope=%s duration_ms=%.2f",
        project_id,
        payload.scope,
        graph_duration_ms,
    )

    action = graph_result.get("action")
    if hasattr(action, "model_dump"):
        action_data = action.model_dump()
    elif isinstance(action, dict):
        action_data = action
    else:
        action_data = {"action": "finish", "reason": "No action was produced."}

    response = ProjectAIResponse(
        action=action_data,
        message=graph_result.get("message") or "No additional AI action is required for the current request.",
        requires_approval=bool(graph_result.get("requires_approval")),
        proposal=graph_result.get("proposal"),
    )
    proposal = response.proposal
    proposal_type = proposal.get("type") if isinstance(proposal, dict) else None
    proposal_data = proposal.get("data") if isinstance(proposal, dict) else None
    proposed_task_count = (
        len(proposal_data.get("tasks", []))
        if isinstance(proposal_data, dict)
        and isinstance(proposal_data.get("tasks"), list)
        else 0
    )
    logger.info(
        "AI workflow response ready project_id=%s scope=%s action=%s proposal_type=%s task_count=%s",
        project_id,
        payload.scope,
        response.action.action,
        proposal_type or "none",
        proposed_task_count,
    )
    return response


@router.post(
    "/{project_id}/ai/execute",
    response_model=PlanExecutionResponse,
)
def execute_accepted_plan_route(
    project_id: int,
    payload: PlanExecutionRequest,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        validate_accepted_plan(
            db=db,
            project_id=project_id,
            plan=payload.plan,
            scope=payload.scope,
            part_id=payload.part_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        graph = build_completion_graph(db)
        graph_result = graph.invoke(
            {
                "project_id": project_id,
                "scope": payload.scope,
                "part_id": payload.part_id,
                "user_request": payload.user_request or payload.plan.objective,
                "accepted_plan": payload.plan,
                "task_results": [],
                "status": "pending",
            }
        )
    except Exception as error:
        logger.exception(
            "Accepted-plan completion graph failed project_id=%s",
            project_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Draft generation request failed.",
        ) from error

    return PlanExecutionResponse(
        project_id=project_id,
        status=graph_result["status"],
        objective=payload.plan.objective,
        tasks=graph_result["task_results"],
    )


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
