from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import Finding, Part, Project, Source
from app.schemas import FindingCreate, FindingResponse, FindingUpdate

router = APIRouter(prefix="/api", tags=["findings"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_finding_or_404(finding_id: int, db: Session) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


def get_project_items_for_finding(
    project_id: int,
    item_ids: list[int],
    model: type[Part] | type[Source],
    db: Session,
) -> list[Part] | list[Source]:
    if not item_ids:
        return []
    items = db.scalars(
        select(model).where(model.project_id == project_id, model.id.in_(set(item_ids)))
    ).all()
    if len(items) != len(set(item_ids)):
        raise HTTPException(
            status_code=422,
            detail=f"All {model.__name__}s must belong to the Finding's Project",
        )
    return items


@router.post("/projects/{project_id}/findings", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
def create_finding(project_id: int, payload: FindingCreate, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    data = payload.model_dump(exclude={"part_ids", "source_ids"})
    finding = Finding(project_id=project_id, **data)
    finding.parts = get_project_items_for_finding(project_id, payload.part_ids, Part, db)
    finding.sources = get_project_items_for_finding(project_id, payload.source_ids, Source, db)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get("/projects/{project_id}/findings", response_model=list[FindingResponse])
def list_findings(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(project_id, db)
    return db.scalars(
        select(Finding).where(Finding.project_id == project_id).order_by(Finding.id)
    ).all()


@router.get("/findings/{finding_id}", response_model=FindingResponse)
def get_finding(finding_id: int, db: Session = Depends(get_db)):
    return get_finding_or_404(finding_id, db)


@router.put("/findings/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: int,
    payload: FindingUpdate,
    db: Session = Depends(get_db),
):
    finding = get_finding_or_404(finding_id, db)
    values = payload.model_dump(exclude_unset=True)

    if "part_ids" in values:
        finding.parts = get_project_items_for_finding(
            finding.project_id,
            values.pop("part_ids") or [],
            Part,
            db,
        )
    if "source_ids" in values:
        finding.sources = get_project_items_for_finding(
            finding.project_id,
            values.pop("source_ids") or [],
            Source,
            db,
        )

    for field, value in values.items():
        setattr(finding, field, value)

    db.commit()
    db.refresh(finding)
    return finding


@router.delete("/findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = get_finding_or_404(finding_id, db)
    db.delete(finding)
    db.commit()
