from app.agents.planner.planner import ProjectPlanner
from app.agents.planner.schemas import PlannerInput
from app.context.service import ContextService
from app.db.database import SessionLocal


db = SessionLocal()

try:
    # 1. Retrieve project context
    context_service = ContextService(db)
    context = context_service.get_planner_context(project_id=1)

    # 2. Create planner
    planner = ProjectPlanner()

    # 3. Give the planner an objective
    planner_input = PlannerInput(
        objective="""
        Build a project explaining whether India can become
        a major semiconductor manufacturing hub.

        Focus on semiconductor fabs, ATMP/OSAT,
        infrastructure, supply chains, capital requirements,
        technology, government incentives, and India's
        ability to compete with other manufacturing countries.
        """,
        relevant_context=context,
    )

    # 4. Ask planner for a plan
    result = planner.plan(planner_input)

    print("\nPROJECT PLAN")
    print("============")

    print("Title:", result.title)
    print("Summary:", result.summary)

    print("\nPARTS")
    print("-----")

    for i, part in enumerate(result.parts, start=1):
        print(f"\n{i}. {part.title}")
        print("Objective:", part.objective)
        print("Description:", part.description)

finally:
    db.close()