from app.agents.planner.planner import ProjectPlanner
from app.agents.planner.schemas import PlannerInput


planner = ProjectPlanner()


# ============================================================
# TEST 1: Initial planning
# ============================================================

print("\n" + "=" * 60)
print("TEST 1: INITIAL PROJECT PLAN")
print("=" * 60)

initial_input = PlannerInput(
    objective="""
    Build a project about India's semiconductor industry.
    The project should explain the industry's development,
    major companies, government policies, manufacturing,
    challenges, and future opportunities.
    """,
)

plan_v1 = planner.plan(initial_input)

print("\n[PLAN V1]")
print(plan_v1)

print("\n[PARTS V1]")
for index, part in enumerate(plan_v1.parts, start=1):
    print(f"\nPart {index}: {part.title}")
    print(f"Objective: {part.objective}")
    print(f"Description: {part.description}")


# ============================================================
# TEST 2: User gives feedback and asks for replanning
# ============================================================

print("\n" + "=" * 60)
print("TEST 2: REPLAN BASED ON USER FEEDBACK")
print("=" * 60)

replan_input = PlannerInput(
    objective=initial_input.objective,
    current_plan=plan_v1,
    user_feedback="""
    I don't want this project to focus so much on the general
    semiconductor industry or software/design.

    I want the project to focus specifically on whether India
    can become a major semiconductor manufacturing hub.

    Give much more importance to fabs, ATMP/OSAT,
    infrastructure, supply chains, capital requirements,
    technology, government incentives, and India's ability
    to compete with other manufacturing countries.
    """,
)

plan_v2 = planner.plan(replan_input)

print("\n[PLAN V2]")
print(plan_v2)

print("\n[PARTS V2]")
for index, part in enumerate(plan_v2.parts, start=1):
    print(f"\nPart {index}: {part.title}")
    print(f"Objective: {part.objective}")
    print(f"Description: {part.description}")


# ============================================================
# Basic validation
# ============================================================

print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

assert plan_v1.parts
assert plan_v2.parts

print("Plan V1 type:", type(plan_v1))
print("Plan V2 type:", type(plan_v2))

print("\nPlanner test completed successfully.")