from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import Part, Project, Source
from app.schemas import SourceCreate, SourceResponse, SourceUpdate

router = APIRouter(prefix="/api/projects/{project_id}/sources", tags=["sources"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_source_or_404(project_id: int, source_id: int, db: Session) -> Source:
    source = db.scalar(
        select(Source).where(Source.id == source_id, Source.project_id == project_id)
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


def get_parts_for_source(project_id: int, part_ids: list[int], db: Session) -> list[Part]:
    if not part_ids:
        return []
    parts = db.scalars(
        select(Part).where(Part.project_id == project_id, Part.id.in_(set(part_ids)))
    ).all()
    if len(parts) != len(set(part_ids)):
        raise HTTPException(status_code=422, detail="All Parts must belong to the Source's Project")
    return parts


@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    project_id: int,
    source: SourceCreate,
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, db)
    source_values = source.model_dump()
    source_values["metadata_"] = source_values.pop("metadata")
    part_ids = source_values.pop("part_ids")
    new_source = Source(project_id=project_id, **source_values)
    new_source.parts = get_parts_for_source(project_id, part_ids, db)
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return new_source


@router.get("/", response_model=list[SourceResponse])
def get_sources(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    return db.scalars(
        select(Source).where(Source.project_id == project_id).order_by(Source.id)
    ).all()


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(project_id: int, source_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    return get_source_or_404(project_id, source_id, db)


@router.put("/{source_id}", response_model=SourceResponse)
def update_source(
    project_id: int,
    source_id: int,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, db)
    source = get_source_or_404(project_id, source_id, db)
    values = payload.model_dump(exclude_unset=True)
    if "part_ids" in values:
        source.parts = get_parts_for_source(project_id, values.pop("part_ids") or [], db)
    for field, value in values.items():
        setattr(source, "metadata_" if field == "metadata" else field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(project_id: int, source_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    source = get_source_or_404(project_id, source_id, db)
    db.delete(source)
    db.commit()
