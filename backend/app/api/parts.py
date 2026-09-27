from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import Part, Project
from app.schemas import (
    PartCommitCreate,
    PartCreate,
    PartResponse,
    PartRevisionDetailResponse,
    PartRevisionResponse,
    PartUpdate,
)
from app.services.part_history import (
    create_part_commit,
    get_part_revision,
    list_part_revisions,
    restore_part_revision,
)

router = APIRouter(prefix="/api/projects/{project_id}/parts", tags=["parts"])
history_router = APIRouter(prefix="/api/parts", tags=["part-history"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_part_or_404(project_id: int, part_id: int, db: Session) -> Part:
    part = db.scalar(
        select(Part).where(Part.id == part_id, Part.project_id == project_id)
    )
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")
    return part


@router.post("/", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
def create_part(project_id: int, payload: PartCreate, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    part = Part(project_id=project_id, **payload.model_dump())
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


@router.get("/", response_model=list[PartResponse])
def get_parts(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    return db.scalars(
        select(Part).where(Part.project_id == project_id).order_by(Part.position, Part.id)
    ).all()


@router.get("/{part_id}", response_model=PartResponse)
def get_part(project_id: int, part_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    return get_part_or_404(project_id, part_id, db)


@router.put("/{part_id}", response_model=PartResponse)
def update_part(
    project_id: int,
    part_id: int,
    payload: PartUpdate,
    db: Session = Depends(get_db),
):
    get_project_or_404(project_id, db)
    part = get_part_or_404(project_id, part_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    db.commit()
    db.refresh(part)
    return part


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part(project_id: int, part_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    part = get_part_or_404(project_id, part_id, db)
    db.delete(part)
    db.commit()


@history_router.post(
    "/{part_id}/commits",
    response_model=PartRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_part_commit_route(
    part_id: int,
    payload: PartCommitCreate,
    db: Session = Depends(get_db),
):
    return create_part_commit(part_id, payload.commit_message, db, payload.script_revision_id)


@history_router.get("/{part_id}/commits", response_model=list[PartRevisionResponse])
def list_part_commits(part_id: int, db: Session = Depends(get_db)):
    return list_part_revisions(part_id, db)


@history_router.get(
    "/{part_id}/commits/{revision_id}",
    response_model=PartRevisionDetailResponse,
)
def get_part_commit_detail(part_id: int, revision_id: int, db: Session = Depends(get_db)):
    return get_part_revision(part_id, revision_id, db)


@history_router.post(
    "/{part_id}/commits/{revision_id}/restore",
    response_model=PartRevisionResponse,
)
def restore_part_commit(part_id: int, revision_id: int, db: Session = Depends(get_db)):
    return restore_part_revision(part_id, revision_id, db)