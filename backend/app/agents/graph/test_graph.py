from app.agents.graph.graph import build_graph


graph = build_graph()


initial_state = {
    "project_id": 1,
    "scope": "project",
    "part_id": None,
    "user_message": """
    Build a project explaining whether India can become
    a major semiconductor manufacturing hub.

    Focus on fabs, ATMP/OSAT, infrastructure, supply chains,
    capital requirements, technology, government incentives,
    and India's ability to compete with other manufacturing
    countries.
    """,
    "user_objective": "Build a project explaining whether India can become a major semiconductor manufacturing hub.",
    "current_proposal": None,
    "context": None,
    "action": None,
    "plan": None,
    "message": None,
    "requires_approval": False,
    "proposal": None,
}


result = graph.invoke(initial_state)


print("\nACTION")
print("======")
print(result["action"])

print("\nCONTEXT")
print("=======")
print("Project:", result["context"].project_name)
print("Parts:", len(result["context"].current_parts))
print("Findings:", len(result["context"].relevant_findings))

print("\nPLAN")
print("====")

plan = result["plan"]

print("Title:", plan.title)
print("Summary:", plan.summary)

for index, part in enumerate(plan.parts, start=1):
    print(f"\n{index}. {part.title}")
    print("Objective:", part.objective)