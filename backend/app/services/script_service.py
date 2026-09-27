from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Part, Script, ScriptDraft, ScriptRevision


def _get_part_or_404(part_id: int, db: Session) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    return part


def _get_script_or_404(script_id: int, db: Session) -> Script:
    script = db.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return script


def _get_draft_or_404(draft_id: int, db: Session) -> ScriptDraft:
    draft = db.get(ScriptDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script draft not found")
    return draft


def _serialize_draft(draft: ScriptDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "part_id": draft.part_id,
        "title": draft.title,
        "content": draft.content,
        "created_by_type": draft.created_by_type,
        "status": draft.status,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }


def _serialize_script(script: Script) -> dict[str, Any]:
    return {
        "id": script.id,
        "part_id": script.part_id,
        "current_revision_id": script.current_revision_id,
        "created_at": script.created_at,
        "updated_at": script.updated_at,
    }


def _serialize_revision(revision: ScriptRevision) -> dict[str, Any]:
    return {
        "id": revision.id,
        "script_id": revision.script_id,
        "revision_number": revision.revision_number,
        "content": revision.content,
        "created_by_type": revision.created_by_type,
        "commit_message": revision.commit_message,
        "created_at": revision.created_at,
        "source_draft_id": revision.source_draft_id,
    }


def create_script_draft(part_id: int, draft_data: dict[str, Any], db: Session) -> dict[str, Any]:
    part = _get_part_or_404(part_id, db)
    draft = ScriptDraft(
        part_id=part.id,
        title=draft_data.get("title"),
        content=draft_data.get("content"),
        created_by_type=draft_data.get("created_by_type", "user"),
        status="active",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


def list_script_drafts(part_id: int, db: Session) -> list[dict[str, Any]]:
    _get_part_or_404(part_id, db)
    drafts = db.scalars(
        select(ScriptDraft).where(ScriptDraft.part_id == part_id).order_by(ScriptDraft.created_at.desc())
    ).all()
    return [_serialize_draft(draft) for draft in drafts]


def get_script_draft(draft_id: int, db: Session) -> dict[str, Any]:
    return _serialize_draft(_get_draft_or_404(draft_id, db))


def update_script_draft(draft_id: int, updates: dict[str, Any], db: Session) -> dict[str, Any]:
    draft = _get_draft_or_404(draft_id, db)
    for field, value in updates.items():
        if field in {"title", "content", "created_by_type", "status"}:
            setattr(draft, field, value)
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


def accept_script_draft(draft_id: int, db: Session) -> dict[str, Any]:
    draft = _get_draft_or_404(draft_id, db)
    part = _get_part_or_404(draft.part_id, db)

    script = db.scalar(select(Script).where(Script.part_id == part.id))
    if script is None:
        script = Script(part_id=part.id)
        db.add(script)
        db.flush()

    revision_number = (
        db.scalar(
            select(func.coalesce(func.max(ScriptRevision.revision_number), 0)).where(
                ScriptRevision.script_id == script.id
            )
        )
        or 0
    ) + 1

    revision = ScriptRevision(
        script_id=script.id,
        revision_number=revision_number,
        content=draft.content,
        created_by_type=draft.created_by_type,
        commit_message=f"Accepted draft {draft.title or draft.id}",
        source_draft_id=draft.id,
    )
    db.add(revision)
    db.flush()

    script.current_revision_id = revision.id
    script.updated_at = revision.created_at
    draft.status = "accepted"
    draft.updated_at = revision.created_at
    db.commit()
    db.refresh(script)
    db.refresh(revision)
    db.refresh(draft)
    payload = _serialize_revision(revision)
    payload["status"] = draft.status
    return payload


def get_part_script(part_id: int, db: Session) -> dict[str, Any]:
    part = _get_part_or_404(part_id, db)
    script = db.scalar(select(Script).where(Script.part_id == part.id))
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return _serialize_script(script)


def list_script_revisions(script_id: int, db: Session) -> list[dict[str, Any]]:
    script = _get_script_or_404(script_id, db)
    revisions = db.scalars(
        select(ScriptRevision)
        .where(ScriptRevision.script_id == script.id)
        .order_by(ScriptRevision.revision_number.desc())
    ).all()
    return [_serialize_revision(revision) for revision in revisions]


def get_script_revision(script_id: int, revision_id: int, db: Session) -> dict[str, Any]:
    _get_script_or_404(script_id, db)
    revision = db.scalar(
        select(ScriptRevision).where(
            ScriptRevision.id == revision_id,
            ScriptRevision.script_id == script_id,
        )
    )
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script revision not found")
    return _serialize_revision(revision)


def restore_script_revision(
    script_id: int,
    revision_id: int,
    created_by_type: str,
    db: Session,
) -> dict[str, Any]:
    script = _get_script_or_404(script_id, db)
    revision = db.scalar(
        select(ScriptRevision).where(
            ScriptRevision.id == revision_id,
            ScriptRevision.script_id == script_id,
        )
    )
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script revision not found")

    next_revision_number = (
        db.scalar(
            select(func.coalesce(func.max(ScriptRevision.revision_number), 0)).where(
                ScriptRevision.script_id == script.id
            )
        )
        or 0
    ) + 1

    restored = ScriptRevision(
        script_id=script.id,
        revision_number=next_revision_number,
        content=revision.content,
        created_by_type=created_by_type,
        commit_message=f"Restored from revision {revision.revision_number}",
        source_draft_id=revision.source_draft_id,
    )
    db.add(restored)
    db.flush()

    script.current_revision_id = restored.id
    db.commit()
    db.refresh(restored)
    return _serialize_revision(restored)
