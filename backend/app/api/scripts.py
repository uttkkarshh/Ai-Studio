from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import Part
from app.schemas import (
    ScriptAcceptanceResponse,
    ScriptDraftCreate,
    ScriptDraftResponse,
    ScriptDraftUpdate,
    ScriptResponse,
    ScriptRevisionDetailResponse,
    ScriptRevisionResponse,
)
from app.services.script_service import (
    accept_script_draft,
    create_script_draft,
    get_part_script,
    get_script_draft,
    get_script_revision,
    list_script_drafts,
    list_script_revisions,
    restore_script_revision,
    update_script_draft,
)

router = APIRouter(prefix="/api", tags=["scripts"])


@router.post("/parts/{part_id}/script-drafts", response_model=ScriptDraftResponse, status_code=status.HTTP_201_CREATED)
def create_script_draft_route(part_id: int, payload: ScriptDraftCreate, db: Session = Depends(get_db)):
    return create_script_draft(part_id, payload.model_dump(), db)


@router.get("/parts/{part_id}/script-drafts", response_model=list[ScriptDraftResponse])
def list_script_drafts_route(part_id: int, db: Session = Depends(get_db)):
    return list_script_drafts(part_id, db)


@router.get("/script-drafts/{draft_id}", response_model=ScriptDraftResponse)
def get_script_draft_route(draft_id: int, db: Session = Depends(get_db)):
    return get_script_draft(draft_id, db)


@router.put("/script-drafts/{draft_id}", response_model=ScriptDraftResponse)
def update_script_draft_route(draft_id: int, payload: ScriptDraftUpdate, db: Session = Depends(get_db)):
    return update_script_draft(draft_id, payload.model_dump(exclude_unset=True), db)


@router.post("/script-drafts/{draft_id}/accept", response_model=ScriptAcceptanceResponse)
def accept_script_draft_route(draft_id: int, db: Session = Depends(get_db)):
    return accept_script_draft(draft_id, db)


@router.get("/parts/{part_id}/script", response_model=ScriptResponse)
def get_part_script_route(part_id: int, db: Session = Depends(get_db)):
    return get_part_script(part_id, db)


@router.get("/scripts/{script_id}/revisions", response_model=list[ScriptRevisionResponse])
def list_script_revisions_route(script_id: int, db: Session = Depends(get_db)):
    return list_script_revisions(script_id, db)


@router.get("/scripts/{script_id}/revisions/{revision_id}", response_model=ScriptRevisionDetailResponse)
def get_script_revision_route(script_id: int, revision_id: int, db: Session = Depends(get_db)):
    return get_script_revision(script_id, revision_id, db)


@router.post("/scripts/{script_id}/revisions/{revision_id}/restore", response_model=ScriptRevisionResponse)
def restore_script_revision_route(
    script_id: int,
    revision_id: int,
    payload: dict[str, str] | None = None,
    db: Session = Depends(get_db),
):
    created_by_type = (payload or {}).get("created_by_type", "user")
    return restore_script_revision(script_id, revision_id, created_by_type, db)
