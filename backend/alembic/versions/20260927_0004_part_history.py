"""Add Part revision history and historical association snapshots.

Revision ID: 20260927_0004
Revises: 20260926_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20260927_0004"
down_revision = "20260926_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "part_revisions" not in tables:
        op.create_table(
            "part_revisions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("part_id", sa.Integer(), nullable=False),
            sa.Column("revision_number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("objective", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("commit_message", sa.String(length=1000), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.String(length=100), nullable=False),
            sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("part_id", "revision_number", name="uq_part_revisions_part_revision_number"),
        )
        op.create_index("ix_part_revisions_part_id", "part_revisions", ["part_id"], unique=False)

    if "part_revision_sources" not in tables:
        op.create_table(
            "part_revision_sources",
            sa.Column("revision_id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["revision_id"], ["part_revisions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("revision_id", "source_id"),
        )
        op.create_index(
            "ix_part_revision_sources_revision_id",
            "part_revision_sources",
            ["revision_id"],
            unique=False,
        )

    if "part_revision_assets" not in tables:
        op.create_table(
            "part_revision_assets",
            sa.Column("revision_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["revision_id"], ["part_revisions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("revision_id", "asset_id"),
        )
        op.create_index(
            "ix_part_revision_assets_revision_id",
            "part_revision_assets",
            ["revision_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "part_revision_assets" in tables:
        op.drop_index("ix_part_revision_assets_revision_id", table_name="part_revision_assets")
        op.drop_table("part_revision_assets")
    if "part_revision_sources" in tables:
        op.drop_index("ix_part_revision_sources_revision_id", table_name="part_revision_sources")
        op.drop_table("part_revision_sources")
    if "part_revisions" in tables:
        op.drop_index("ix_part_revisions_part_id", table_name="part_revisions")
        op.drop_table("part_revisions")
