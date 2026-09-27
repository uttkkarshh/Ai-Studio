from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


part_sources = Table(
    "part_sources",
    Base.metadata,
    Column("part_id", ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)
part_assets = Table(
    "part_assets",
    Base.metadata,
    Column("part_id", ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)
part_revision_sources = Table(
    "part_revision_sources",
    Base.metadata,
    Column("revision_id", ForeignKey("part_revisions.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)
part_revision_assets = Table(
    "part_revision_assets",
    Base.metadata,
    Column("revision_id", ForeignKey("part_revisions.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="parts")
    sources: Mapped[list["Source"]] = relationship(
        secondary=part_sources,
        back_populates="parts",
    )
    assets: Mapped[list["Asset"]] = relationship(
        secondary=part_assets,
        back_populates="parts",
    )
    outgoing_relationships: Mapped[list["PartRelationship"]] = relationship(
        foreign_keys="PartRelationship.from_part_id",
        back_populates="from_part",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["PartRelationship"]] = relationship(
        foreign_keys="PartRelationship.to_part_id",
        back_populates="to_part",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list["PartRevision"]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    script: Mapped["Script | None"] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    script_drafts: Mapped[list["ScriptDraft"]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    findings: Mapped[list["Finding"]] = relationship(
        secondary="finding_parts",
        back_populates="parts",
    )


class PartRevision(Base):
    __tablename__ = "part_revisions"
    __table_args__ = (
        UniqueConstraint("part_id", "revision_number", name="uq_part_revisions_part_revision_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    commit_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="user")
    script_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    part: Mapped[Part] = relationship(back_populates="revisions")
    script_revision: Mapped["ScriptRevision | None"] = relationship(
        back_populates="part_revisions",
        foreign_keys=[script_revision_id],
    )
    sources: Mapped[list["Source"]] = relationship(
        secondary=part_revision_sources,
        back_populates="part_revisions",
    )
    assets: Mapped[list["Asset"]] = relationship(
        secondary=part_revision_assets,
        back_populates="part_revisions",
    )


class PartRelationship(Base):
    __tablename__ = "part_relationships"
    __table_args__ = (
        UniqueConstraint("from_part_id", "to_part_id", "relationship_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    from_part: Mapped[Part] = relationship(
        foreign_keys=[from_part_id], back_populates="outgoing_relationships"
    )
    to_part: Mapped[Part] = relationship(
        foreign_keys=[to_part_id], back_populates="incoming_relationships"
    )