import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.completion_agent.completer import CompletionAgent
from app.agents.completion_agent.execution import (
    execute_accepted_plan,
    validate_accepted_plan,
)
from app.agents.completion_agent.schemas import (
    CompletionTaskInput,
    FindingCompletionGeneration,
    PartCompletionGeneration,
    ScriptDraftCompletionGeneration,
    SourceCompletionGeneration,
)
from app.agents.graph.graph import build_completion_graph
from app.agents.work_planner.schemas import WorkPlan, WorkTask
from app.api import projects as projects_module
from app.context.schemas import PlannerContext
from app.db.database import Base
from app.db.dependencies import get_db
from app.main import app
from app.models import Part, Project, ScriptDraft, Source
from app.schemas import FindingCreate, PartCreate, ScriptDraftCreate, SourceCreate


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def make_task(
    capability="create_part",
    action="create",
    target_type="part",
    task_id="task-1",
):
    return WorkTask(
        task_id=task_id,
        title=f"Generate {target_type}",
        action=action,
        capability=capability,
        target_type=target_type,
        intent=f"Create a useful {target_type} draft.",
        expected_output=f"A complete {target_type} draft.",
        completion_criteria=["The draft satisfies the intended goal."],
    )


class FakeStructuredModel:
    def __init__(self, result):
        self.result = result

    def invoke(self, messages):
        return self.result


class FakeModel:
    def __init__(self, result):
        self.result = result
        self.requested_schema = None

    def with_structured_output(self, schema, method):
        self.requested_schema = schema
        return FakeStructuredModel(self.result)


@pytest.mark.parametrize(
    ("task", "generation", "expected_schema"),
    [
        (
            make_task(),
            PartCompletionGeneration(
                status="draft_ready",
                draft={"title": "Audience research"},
            ),
            PartCreate,
        ),
        (
            make_task("create_finding", target_type="finding"),
            FindingCompletionGeneration(
                status="draft_ready",
                draft={"heading": "Audience needs"},
            ),
            FindingCreate,
        ),
        (
            make_task("create_source", target_type="source"),
            SourceCompletionGeneration(
                status="draft_ready",
                draft={"title": "Research note", "source_type": "note"},
            ),
            SourceCreate,
        ),
        (
            make_task(
                "generate_script_draft",
                action="generate_draft",
                target_type="script_draft",
            ),
            ScriptDraftCompletionGeneration(
                status="draft_ready",
                draft={
                    "title": "Opening",
                    "content": {"text": "A concise opening."},
                    "created_by_type": "ai",
                },
            ),
            ScriptDraftCreate,
        ),
    ],
)
def test_completion_agent_generates_schema_valid_target_drafts(
    task,
    generation,
    expected_schema,
):
    model = FakeModel(generation)
    completion_agent = CompletionAgent(model)
    task_input = CompletionTaskInput(
        project_id=1,
        scope="project",
        user_request="Prepare audience research content.",
        task=task,
        project_context=PlannerContext(
            project_id=1,
            project_name="Audience project",
            project_description=None,
            project_objective="Understand the audience",
            current_parts=[],
            relevant_findings=[],
        ),
        target_instructions="Create a complete target-specific draft.",
    )

    result = completion_agent.complete(task_input)

    assert result.status == "draft_ready"
    assert isinstance(result.draft, expected_schema)
    assert model.requested_schema is not None


def test_completion_agent_rejects_invalid_model_output():
    completion_agent = CompletionAgent(
        FakeModel(
            {
                "status": "draft_ready",
                "draft": {"title": "Audience", "project_id": 41},
            }
        )
    )
    task_input = CompletionTaskInput(
        project_id=1,
        scope="project",
        user_request="Create a Part.",
        task=make_task(),
        project_context=PlannerContext(
            project_id=1,
            project_name="Audience project",
            project_description=None,
            project_objective=None,
            current_parts=[],
            relevant_findings=[],
        ),
        target_instructions="Create a Part.",
    )

    with pytest.raises(ValidationError):
        completion_agent.complete(task_input)


def test_missing_script_part_returns_clarification_without_model_call(db_session):
    project = Project(name="Script project")
    db_session.add(project)
    db_session.commit()
    plan = WorkPlan(
        objective="Write a script",
        rationale="A script is needed.",
        tasks=[
            make_task(
                "generate_script_draft",
                action="generate_draft",
                target_type="script_draft",
            )
        ],
    )

    class NeverCalledAgent:
        def complete(self, task_input):
            pytest.fail("Completion Agent must not run without a selected Part.")

    result = execute_accepted_plan(
        db=db_session,
        project_id=project.id,
        plan=plan,
        scope="project",
        part_id=None,
        user_request=plan.objective,
        completion_agent=NeverCalledAgent(),
    )

    assert result[0].status == "needs_clarification"
    assert result[0].clarification_questions
    assert result[0].draft is None


def test_unsupported_capability_is_rejected_before_agent_invocation(db_session):
    project = Project(name="Unsupported plan")
    db_session.add(project)
    db_session.commit()
    plan = WorkPlan(
        objective="Research the project",
        rationale="Research is not implemented in this milestone.",
        tasks=[
            make_task(
                capability="research",
                action="research",
                target_type="project",
            )
        ],
    )

    with pytest.raises(ValueError, match="not supported for draft generation"):
        validate_accepted_plan(db_session, project.id, plan, "project", None)


def test_invalid_action_target_combination_is_rejected(db_session):
    project = Project(name="Invalid plan")
    db_session.add(project)
    db_session.commit()
    plan = WorkPlan(
        objective="Create a finding",
        rationale="A finding is needed.",
        tasks=[
            make_task(
                capability="create_source",
                action="create",
                target_type="finding",
            )
        ],
    )

    with pytest.raises(ValueError, match="requires one of target types"):
        validate_accepted_plan(db_session, project.id, plan, "project", None)


def test_completion_endpoint_returns_404_for_nonexistent_project(client):
    response = client.post(
        "/api/projects/999999/ai/execute",
        json={
            "plan": {
                "objective": "Create a Part",
                "rationale": "A Part is needed.",
                "tasks": [
                    make_task().model_dump(),
                ],
            }
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_completion_endpoint_returns_draft_without_persisting(
    client,
    db_session,
    monkeypatch,
):
    project_id = client.post(
        "/api/projects/",
        json={"name": "Completion endpoint"},
    ).json()["id"]

    class FakeAgent:
        def complete(self, task_input):
            return PartCompletionGeneration(
                status="draft_ready",
                draft={
                    "title": "Audience research",
                    "objective": "Understand audience needs.",
                },
            )

    monkeypatch.setattr(
        projects_module,
        "build_completion_graph",
        lambda db: build_completion_graph(db, FakeAgent()),
    )
    response = client.post(
        f"/api/projects/{project_id}/ai/execute",
        json={
            "plan": {
                "objective": "Prepare audience research content.",
                "rationale": "A focused Part is needed.",
                "tasks": [make_task().model_dump()],
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] == "drafts_ready"
    assert body["tasks"][0]["task_id"] == "task-1"
    assert body["tasks"][0]["target_type"] == "part"
    assert body["tasks"][0]["draft"]["title"] == "Audience research"
    assert body["tasks"][0]["requires_user_approval"] is True
    assert db_session.scalar(select(func.count()).select_from(Part)) == 0


def test_multiple_tasks_preserve_order_and_do_not_persist_drafts(db_session):
    project = Project(name="Multi-task project")
    db_session.add(project)
    db_session.commit()
    plan = WorkPlan(
        objective="Create two project structure drafts",
        rationale="Both areas are needed.",
        tasks=[
            make_task(task_id="first"),
            make_task(task_id="second"),
        ],
    )

    class OrderedAgent:
        def __init__(self):
            self.task_ids = []

        def complete(self, task_input):
            self.task_ids.append(task_input.task.task_id)
            return PartCompletionGeneration(
                status="draft_ready",
                draft={"title": f"Draft {task_input.task.task_id}"},
            )

    agent = OrderedAgent()
    result = build_completion_graph(db_session, agent).invoke(
        {
            "project_id": project.id,
            "scope": "project",
            "part_id": None,
            "user_request": plan.objective,
            "accepted_plan": plan,
            "task_results": [],
            "status": "pending",
        }
    )

    assert agent.task_ids == ["first", "second"]
    assert [task.task_id for task in result["task_results"]] == ["first", "second"]
    assert result["status"] == "drafts_ready"
    assert db_session.scalar(select(func.count()).select_from(Part)) == 0
    assert db_session.scalar(select(func.count()).select_from(Source)) == 0
    assert db_session.scalar(select(func.count()).select_from(ScriptDraft)) == 0
