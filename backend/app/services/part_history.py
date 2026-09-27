from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Part, PartRevision, Script, ScriptRevision


def _serialize_revision(revision: PartRevision) -> dict:
    return {
        "id": revision.id,
        "part_id": revision.part_id,
        "revision_number": revision.revision_number,
        "title": revision.title,
        "objective": revision.objective,
        "description": revision.description,
        "status": revision.status,
        "position": revision.position,
        "commit_message": revision.commit_message,
        "created_at": revision.created_at,
        "created_by": revision.created_by,
        "script_revision_id": revision.script_revision_id,
        "sources": [source.id for source in revision.sources],
        "assets": [asset.id for asset in revision.assets],
    }


def _get_part_or_404(part_id: int, db: Session) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    return part


def _validate_part_scope(part: Part) -> None:
    invalid_sources = [source.id for source in part.sources if source.project_id != part.project_id]
    invalid_assets = [asset.id for asset in part.assets if asset.project_id != part.project_id]
    if invalid_sources or invalid_assets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Part associations must belong to the same project as the Part",
        )


def _next_revision_number(part_id: int, db: Session) -> int:
    current_highest = db.scalar(
        select(func.coalesce(func.max(PartRevision.revision_number), 0)).where(
            PartRevision.part_id == part_id
        )
    )
    return int(current_highest) + 1


def _validate_script_revision_for_part(
    part: Part,
    script_revision_id: int | None,
    db: Session,
    *,
    mutate_current_revision: bool = False,
) -> int | None:
    if script_revision_id is None:
        if mutate_current_revision and part.script is not None:
            part.script.current_revision_id = None
        return None

    script_revision = db.get(ScriptRevision, script_revision_id)
    if script_revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script revision not found")

    script = db.get(Script, script_revision.script_id)
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script revision is not attached to a Script",
        )

    if script.part_id != part.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Script revision belongs to a different Part",
        )

    if mutate_current_revision:
        if part.script is None:
            part.script = script
        part.script.current_revision_id = script_revision_id

    return script_revision_id


def create_part_commit(part_id: int, commit_message: str, db: Session, script_revision_id: int | None = None) -> dict:
    part = _get_part_or_404(part_id, db)
    _validate_part_scope(part)

    if script_revision_id is None and part.script is not None and part.script.current_revision_id is not None:
        script_revision_id = part.script.current_revision_id

    script_revision_id = _validate_script_revision_for_part(
        part,
        script_revision_id,
        db,
        mutate_current_revision=False,
    )

    next_revision_number = _next_revision_number(part_id, db)
    revision = PartRevision(
        part_id=part.id,
        revision_number=next_revision_number,
        title=part.title,
        objective=part.objective,
        description=part.description,
        status=part.status,
        position=part.position,
        commit_message=commit_message.strip(),
        created_by="user",
        script_revision_id=script_revision_id,
    )
    revision.sources = list(part.sources)
    revision.assets = list(part.assets)

    db.add(revision)
    db.commit()
    db.refresh(revision)
    return _serialize_revision(revision)


def list_part_revisions(part_id: int, db: Session) -> list[dict]:
    _get_part_or_404(part_id, db)
    revisions = db.scalars(
        select(PartRevision)
        .where(PartRevision.part_id == part_id)
        .order_by(PartRevision.revision_number.desc())
    ).all()
    return [_serialize_revision(revision) for revision in revisions]


def get_part_revision(part_id: int, revision_id: int, db: Session) -> dict:
    _get_part_or_404(part_id, db)
    revision = db.scalar(
        select(PartRevision).where(
            PartRevision.id == revision_id,
            PartRevision.part_id == part_id,
        )
    )
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part revision not found",
        )
    return _serialize_revision(revision)


def restore_part_revision(part_id: int, revision_id: int, db: Session) -> dict:
    part = _get_part_or_404(part_id, db)
    revision = db.scalar(
        select(PartRevision).where(
            PartRevision.id == revision_id,
            PartRevision.part_id == part_id,
        )
    )
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part revision not found",
        )

    invalid_sources = [source.id for source in revision.sources if source.project_id != part.project_id]
    invalid_assets = [asset.id for asset in revision.assets if asset.project_id != part.project_id]
    if invalid_sources or invalid_assets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Revision associations must belong to the same project as the Part",
        )

    restored_script_revision_id = _validate_script_revision_for_part(
        part,
        revision.script_revision_id,
        db,
        mutate_current_revision=True,
    )

    part.title = revision.title
    part.objective = revision.objective
    part.description = revision.description
    part.status = revision.status
    part.position = revision.position
    part.sources = list(revision.sources)
    part.assets = list(revision.assets)

    restored_revision = PartRevision(
        part_id=part.id,
        revision_number=_next_revision_number(part_id, db),
        title=revision.title,
        objective=revision.objective,
        description=revision.description,
        status=revision.status,
        position=revision.position,
        commit_message=f"Restored from revision {revision.revision_number}",
        created_by="user",
        script_revision_id=restored_script_revision_id,
    )
    restored_revision.sources = list(revision.sources)
    restored_revision.assets = list(revision.assets)

    db.add(restored_revision)
    db.commit()
    db.refresh(restored_revision)
    db.refresh(part)
    if part.script is not None:
        db.refresh(part.script)
    return _serialize_revision(restored_revision)
