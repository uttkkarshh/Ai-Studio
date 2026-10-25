from sqlalchemy.orm import Session

from app.context.schemas import (
    FindingContext,
    PartContext,
    PlannerContext,
)
from app.models.part import Part
from app.models.project import Project


class ContextService:

    def __init__(self, db: Session):
        self.db = db

    def _build_planner_context(self, project: Project, selected_part: Part | None = None) -> PlannerContext:
        parts = project.parts

        part_contexts = [
            PartContext(
                id=part.id,
                title=part.title,
                objective=part.objective,
                description=part.description,
                status=part.status,
                position=part.position,
            )
            for part in sorted(parts, key=lambda p: p.position)
        ]

        selected_part_context = None
        if selected_part is not None:
            selected_part_context = PartContext(
                id=selected_part.id,
                title=selected_part.title,
                objective=selected_part.objective,
                description=selected_part.description,
                status=selected_part.status,
                position=selected_part.position,
            )

        finding_contexts = [
            FindingContext(
                id=finding.id,
                heading=finding.heading,
                content=finding.content,
                status=finding.status,
            )
            for finding in project.findings
        ]

        return PlannerContext(
            project_id=project.id,
            project_name=project.name,
            project_description=project.description,
            project_objective=project.objective,
            selected_part=selected_part_context,
            current_parts=part_contexts,
            relevant_findings=finding_contexts,
        )

    def get_planner_context(self, project_id: int) -> PlannerContext:
        project = (
            self.db.query(Project)
            .filter(Project.id == project_id)
            .first()
        )

        if project is None:
            raise ValueError(f"Project {project_id} not found")

        return self._build_planner_context(project)

    def get_project_context(self, project_id: int) -> PlannerContext:
        return self.get_planner_context(project_id)

    def get_part_context(self, project_id: int, part_id: int) -> PlannerContext:
        project = (
            self.db.query(Project)
            .filter(Project.id == project_id)
            .first()
        )

        if project is None:
            raise ValueError(f"Project {project_id} not found")

        part = (
            self.db.query(Part)
            .filter(Part.id == part_id, Part.project_id == project_id)
            .first()
        )

        if part is None:
            raise ValueError(f"Part {part_id} not found for project {project_id}")

        return self._build_planner_context(project, selected_part=part)