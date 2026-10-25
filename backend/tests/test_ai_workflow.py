import json
import logging
from typing import get_args

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.graph import graph as graph_module
from app.agents.orchestrator.orchestrator import Orchestrator
from app.agents.orchestrator.schemas import OrchestratorAction
from app.agents.work_planner.planner import WorkPlanner
from app.agents.work_planner.schemas import WorkPlan, WorkTask
from app.api import projects as projects_module
from app.db.database import Base


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


def make_work_plan(capability="research"):
    return WorkPlan(
        objective="Review project evidence",
        rationale="Evidence gathering is needed.",
        tasks=[
            WorkTask(
                task_id="research-project",
                title="Research the project",
                action="research",
                capability=capability,
                target_type="project",
                intent="Gather relevant evidence.",
                expected_output="A set of relevant evidence.",
                completion_criteria=["Evidence is relevant to the objective."],
            )
        ],
    )


class FakePlannerModel:
    def __init__(self, plan):
        self.plan = plan
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return self.plan


def test_revision_feedback_and_existing_work_plan_reach_work_planner(monkeypatch):
    previous_plan = make_work_plan()
    revised_plan = make_work_plan()
    model = FakePlannerModel(revised_plan)
    monkeypatch.setattr(graph_module, "create_work_planner_model", lambda: model)
    revision_feedback = "Revise the research task to focus on energy requirements."
    action = OrchestratorAction(
        action="revise_plan",
        reason="The user requested a plan revision.",
        objective="Review project energy requirements.",
    )

    result = graph_module.plan_work_node(
        {
            "project_id": 1,
            "scope": "project",
            "part_id": None,
            "user_message": revision_feedback,
            "user_objective": revision_feedback,
            "current_proposal": {
                "type": "work_plan",
                "data": previous_plan.model_dump(),
            },
            "context": {"project_name": "Energy project"},
            "action": action,
            "plan": None,
            "message": None,
            "requires_approval": False,
            "proposal": None,
        }
    )

    assert result["plan"] == revised_plan
    assert result["proposal"] == {
        "type": "work_plan",
        "data": revised_plan.model_dump(),
    }
    assert result["requires_approval"] is True

    human_message = model.messages[1][1]
    assert "Objective:\nReview project energy requirements." in human_message
    planner_context = json.loads(human_message.split("\n\nContext:\n", 1)[1])
    assert planner_context["project_context"] == {"project_name": "Energy project"}
    assert planner_context["existing_work_plan"] == previous_plan.model_dump()
    assert planner_context["request_type"] == "revise_plan"
    assert planner_context["revision_feedback"] == revision_feedback


def test_work_planner_rejects_unregistered_capability():
    planner = WorkPlanner(FakePlannerModel(make_work_plan(capability="unknown_capability")))

    with pytest.raises(ValueError, match="Unsupported capability"):
        planner.plan("Review project evidence")


def test_new_project_prompt_requests_tailored_part_creation_tasks():
    initial_plan = WorkPlan(
        objective="Explain coastal flood resilience",
        rationale="The project needs distinct research areas.",
        tasks=[
            WorkTask(
                task_id="create-risk-part",
                title="Create a coastal flood-risk Part",
                action="create",
                capability="create_part",
                target_type="part",
                intent="Organize exposure and hazard analysis.",
                expected_output="A Part focused on coastal flood risk.",
                completion_criteria=["The Part covers flood hazards and exposure."],
            ),
        ],
    )
    model = FakePlannerModel(initial_plan)
    planner = WorkPlanner(model)
    context = json.dumps({
        "project_context": {
            "project_name": "Coastal resilience",
            "current_parts": [],
            "selected_part": None,
        },
        "existing_work_plan": None,
    })

    plan = planner.plan("Explain coastal flood resilience", context)

    assert plan == initial_plan
    assert "currently has no Parts" in model.messages[0][1]
    assert "tailored create_part tasks" in model.messages[0][1]


def test_existing_parts_context_discourages_duplicate_part_creation():
    model = FakePlannerModel(make_work_plan())
    planner = WorkPlanner(model)
    context = json.dumps({
        "project_context": {
            "current_parts": [
                {"id": 4, "title": "Flood hazards", "objective": "Map coastal exposure."}
            ],
            "selected_part": None,
        },
        "existing_work_plan": None,
    })

    planner.plan("Review current evidence", context)

    assert "already has Parts" in model.messages[0][1]
    assert "do not propose duplicate create_part tasks" in model.messages[0][1]


def test_revision_does_not_repeat_part_creation_already_in_current_work_plan():
    current_plan = WorkPlan(
        objective="Set up a coastal resilience project",
        rationale="The project needs a structure.",
        tasks=[
            WorkTask(
                task_id="create-risk-part",
                title="Create a flood-risk Part",
                action="create",
                capability="create_part",
                target_type="part",
                intent="Organize risk analysis.",
                expected_output="A flood-risk Part.",
                completion_criteria=["The Part covers flood risk."],
            )
        ],
    )
    model = FakePlannerModel(make_work_plan())
    planner = WorkPlanner(model)
    context = json.dumps({
        "project_context": {"current_parts": [], "selected_part": None},
        "existing_work_plan": current_plan.model_dump(),
        "request_type": "revise_plan",
    })

    planner.plan("Refine the project plan", context)

    assert "existing WorkPlan already proposes Part creation" in model.messages[0][1]


def test_part_scoped_context_discourages_project_structure_tasks():
    model = FakePlannerModel(make_work_plan())
    planner = WorkPlanner(model)
    context = json.dumps({
        "project_context": {
            "current_parts": [{"id": 4, "title": "Flood hazards"}],
            "selected_part": {"id": 4, "title": "Flood hazards"},
        },
        "existing_work_plan": None,
    })

    planner.plan("Review this Part", context)

    assert "scoped to the selected Part" in model.messages[0][1]
    assert "do not propose create_part tasks" in model.messages[0][1]


def test_orchestrator_actions_all_have_graph_routes():
    actions = get_args(OrchestratorAction.model_fields["action"].annotation)
    for action_name in actions:
        action = OrchestratorAction(
            action=action_name,
            reason="Test action routing.",
            objective="Test objective.",
        )
        route = graph_module.route_after_orchestrator({"action": action})
        assert route == (
            "plan_work"
            if action_name in {"create_plan", "revise_plan", "generate_script"}
            else graph_module.END
        )


def test_unsupported_orchestrator_action_falls_back_without_execution():
    class FakeDecisionModel:
        def invoke(self, prompt):
            return {
                "action": "execute_tasks",
                "reason": "Unsupported action.",
                "objective": "Run proposed tasks.",
            }

    action = Orchestrator(FakeDecisionModel()).decide(
        user_message="What is the project objective?"
    )

    assert action.action == "answer"
    assert "does not clearly require a workflow action" in action.reason


def test_ai_api_serializes_work_plan_proposal_without_creating_parts(client, monkeypatch):
    plan = make_work_plan()

    class FakeGraph:
        def invoke(self, state):
            assert state["current_proposal"] is None
            return {
                "action": OrchestratorAction(
                    action="create_plan",
                    reason="A structured plan was requested.",
                    objective=plan.objective,
                ),
                "message": "I prepared a work plan for your review.",
                "requires_approval": True,
                "proposal": {"type": "work_plan", "data": plan.model_dump()},
            }

    monkeypatch.setattr(projects_module, "build_graph", lambda: FakeGraph())
    project_id = client.post("/api/projects/", json={"name": "AI workflow"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/ai/message",
        json={"message": "Create a work plan.", "scope": "project"},
    )

    assert response.status_code == 200
    assert response.json()["proposal"] == {
        "type": "work_plan",
        "data": plan.model_dump(),
    }
    assert response.json()["requires_approval"] is True
    assert client.get(f"/api/projects/{project_id}/parts/").json() == []


def test_part_scoped_generate_script_returns_reviewable_script_plan_without_persisting(
    client,
    monkeypatch,
):
    project_id = client.post(
        "/api/projects/",
        json={"name": "Script generation"},
    ).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Opening", "objective": "Introduce the topic."},
    ).json()["id"]
    plan = WorkPlan(
        objective="Generate an opening script for the selected Part.",
        rationale="The user requested a script draft for this Part.",
        tasks=[
            WorkTask(
                task_id="generate-opening-script",
                title="Generate an opening script",
                action="generate_draft",
                capability="generate_script_draft",
                target_type="script_draft",
                intent="Write an opening script for the selected Part.",
                expected_output="An unpersisted, reviewable script draft.",
                completion_criteria=["The draft introduces the Part's topic."],
            )
        ],
    )

    class FakeOrchestrator:
        def decide(self, **kwargs):
            assert kwargs["scope"] == "part"
            assert kwargs["part_id"] == part_id
            return OrchestratorAction(
                action="generate_script",
                reason="The user requested a script for the selected Part.",
                objective=plan.objective,
            )

    class FakePlannerModel:
        def invoke(self, messages):
            assert "exactly one task" in messages[0][1]
            assert "generate_script_draft" in messages[0][1]
            return plan

    monkeypatch.setattr(graph_module, "Orchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        graph_module,
        "_load_context_for_state",
        lambda state: {
            "current_parts": [{"id": part_id, "title": "Opening"}],
            "selected_part": {"id": part_id, "title": "Opening"},
        },
    )
    monkeypatch.setattr(
        graph_module,
        "create_work_planner_model",
        lambda: FakePlannerModel(),
    )

    response = client.post(
        f"/api/projects/{project_id}/ai/message",
        json={
            "message": "Generate a script for this part.",
            "scope": "part",
            "part_id": part_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"]["action"] == "generate_script"
    assert body["message"] == "I prepared a script-generation plan for your review."
    assert body["requires_approval"] is True
    assert body["proposal"] == {"type": "work_plan", "data": plan.model_dump()}
    assert client.get(f"/api/parts/{part_id}/script-drafts").json() == []


def test_unsupported_research_action_returns_clear_message(client, monkeypatch):
    project_id = client.post(
        "/api/projects/",
        json={"name": "Unsupported research"},
    ).json()["id"]

    class FakeOrchestrator:
        def decide(self, **kwargs):
            return OrchestratorAction(
                action="research",
                reason="The user requested research.",
                objective="Research the project.",
            )

    monkeypatch.setattr(graph_module, "Orchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        graph_module,
        "_load_context_for_state",
        lambda state: {},
    )

    response = client.post(
        f"/api/projects/{project_id}/ai/message",
        json={"message": "Research the project.", "scope": "project"},
    )

    assert response.status_code == 200
    assert response.json()["action"]["action"] == "research"
    assert response.json()["message"] == (
        "Research is not available in this workflow yet. No research was "
        "performed; choose a work-planning request instead."
    )
    assert response.json()["proposal"] is None
    assert response.json()["requires_approval"] is False


def test_ai_api_returns_conversational_response_without_proposal(client, monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            return {
                "action": OrchestratorAction(
                    action="answer",
                    reason="This is a conversational response.",
                    objective="",
                ),
                "message": "Here is the answer.",
                "requires_approval": False,
                "proposal": None,
            }

    monkeypatch.setattr(projects_module, "build_graph", lambda: FakeGraph())
    project_id = client.post("/api/projects/", json={"name": "Conversational response"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/ai/message",
        json={"message": "What does this project do?", "scope": "project"},
    )

    assert response.status_code == 200
    assert response.json()["action"]["action"] == "answer"
    assert response.json()["message"] == "Here is the answer."
    assert response.json()["proposal"] is None
    assert response.json()["requires_approval"] is False


def test_request_id_is_returned_and_correlates_request_and_workflow_logs(
    client,
    monkeypatch,
    caplog,
):
    class FakeGraph:
        def invoke(self, state):
            logging.getLogger("test.workflow").info("fake graph invoked")
            return {
                "action": OrchestratorAction(
                    action="answer",
                    reason="A conversational response.",
                    objective="",
                ),
                "message": "A safe response.",
                "requires_approval": False,
                "proposal": None,
            }

    monkeypatch.setattr(projects_module, "build_graph", lambda: FakeGraph())
    project_id = client.post("/api/projects/", json={"name": "Correlation"}).json()["id"]

    with caplog.at_level(logging.INFO):
        response = client.post(
            f"/api/projects/{project_id}/ai/message",
            json={"message": "Answer conversationally.", "scope": "project"},
        )

    request_id = response.headers["X-Request-ID"]
    correlated_records = [
        record for record in caplog.records
        if getattr(record, "request_id", None) == request_id
    ]
    assert response.status_code == 200
    assert len(request_id) == 36
    assert any("http request started" in record.getMessage() for record in correlated_records)
    assert any("fake graph invoked" in record.getMessage() for record in correlated_records)
    assert any("AI workflow response ready" in record.getMessage() for record in correlated_records)
    assert any("http request completed" in record.getMessage() for record in correlated_records)


def test_unexpected_workflow_failure_is_logged_and_returned_without_details(
    client,
    monkeypatch,
    caplog,
):
    class FakeGraph:
        def invoke(self, state):
            raise RuntimeError("upstream provider unavailable")

    monkeypatch.setattr(projects_module, "build_graph", lambda: FakeGraph())
    project_id = client.post("/api/projects/", json={"name": "Safe error"}).json()["id"]

    with caplog.at_level(logging.ERROR):
        response = client.post(
            f"/api/projects/{project_id}/ai/message",
            json={"message": "Create a WorkPlan.", "scope": "project"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "AI workflow request failed."}
    assert "upstream provider unavailable" not in response.text
    assert "upstream provider unavailable" in caplog.text
    assert any(
        "AI workflow graph failed" in record.getMessage()
        and record.exc_info is not None
        for record in caplog.records
    )
    assert all(
        getattr(record, "request_id", None) == response.headers["X-Request-ID"]
        for record in caplog.records
        if "AI workflow graph failed" in record.getMessage()
    )


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)
def test_local_vite_origins_are_allowed_by_cors(client, origin):
    response = client.options(
        "/api/projects/2/ai/message",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin
