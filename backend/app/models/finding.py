from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


finding_parts = Table(
    "finding_parts",
    Base.metadata,
    Column("finding_id", ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True),
    Column("part_id", ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True),
)

finding_sources = Table(
    "finding_sources",
    Base.metadata,
    Column("finding_id", ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    heading: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        "content",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    created_by_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="findings")
    parts: Mapped[list["Part"]] = relationship(
        secondary=finding_parts,
        back_populates="findings",
    )
    sources: Mapped[list["Source"]] = relationship(
        secondary=finding_sources,
        back_populates="findings",
    )

    @property
    def part_ids(self) -> list[int]:
        return [part.id for part in self.parts]

    @property
    def source_ids(self) -> list[int]:
        return [source.id for source in self.sources]
