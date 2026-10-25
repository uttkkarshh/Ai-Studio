from app.context.service import ContextService
from app.db.database import SessionLocal


db = SessionLocal()

try:
    service = ContextService(db)

    context = service.get_planner_context(project_id=1)

    print("\nPROJECT")
    print("-------")
    print("ID:", context.project_id)
    print("Name:", context.project_name)
    print("Objective:", context.project_objective)

    print("\nPARTS")
    print("-----")

    for part in context.current_parts:
        print(
            part.id,
            "|",
            part.title,
            "|",
            part.status,
        )

    print("\nFINDINGS")
    print("--------")

    for finding in context.relevant_findings:
        print(
            finding.id,
            "|",
            finding.heading,
            "|",
            finding.status,
        )

finally:
    db.close()