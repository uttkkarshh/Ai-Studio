from typing import Any

from pydantic import BaseModel


class PartContext(BaseModel):
    id: int
    title: str
    objective: str | None
    description: str | None
    status: str
    position: int


class FindingContext(BaseModel):
    id: int
    heading: str
    content: dict[str, Any] | list[Any] | None
    status: str


class PlannerContext(BaseModel):
    project_id: int
    project_name: str
    project_description: str | None
    project_objective: str | None
    selected_part: PartContext | None = None

    current_parts: list[PartContext]
    relevant_findings: list[FindingContext]