from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Script(Base):
    __tablename__ = "scripts"
    __table_args__ = (UniqueConstraint("part_id", name="uq_scripts_part_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    part: Mapped["Part"] = relationship(back_populates="script")
    revisions: Mapped[list["ScriptRevision"]] = relationship(
        back_populates="script",
        foreign_keys="ScriptRevision.script_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    current_revision: Mapped["ScriptRevision | None"] = relationship(
        foreign_keys=[current_revision_id],
        post_update=True,
    )


class ScriptDraft(Base):
    __tablename__ = "script_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        "content",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    created_by_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    part: Mapped["Part"] = relationship(back_populates="script_drafts")


class ScriptRevision(Base):
    __tablename__ = "script_revisions"
    __table_args__ = (
        UniqueConstraint("script_id", "revision_number", name="uq_script_revisions_script_revision_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(
        ForeignKey("scripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        "content",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    created_by_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    commit_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    source_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_drafts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    script: Mapped["Script"] = relationship(
        back_populates="revisions",
        foreign_keys=[script_id],
    )
    source_draft: Mapped["ScriptDraft | None"] = relationship(foreign_keys=[source_draft_id])
    part_revisions: Mapped[list["PartRevision"]] = relationship(
        back_populates="script_revision",
        foreign_keys="PartRevision.script_revision_id",
    )
