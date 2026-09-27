"""Add project-level Finding records with part/source links.

Revision ID: 20260929_0006
Revises: 20260928_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0006"
down_revision = "20260928_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "findings" not in tables:
        op.create_table(
            "findings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("heading", sa.String(length=255), nullable=False),
            sa.Column("content", sa.JSON(), nullable=True),
            sa.Column("created_by_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_findings_project_id", "findings", ["project_id"], unique=False)

    if "finding_parts" not in tables:
        op.create_table(
            "finding_parts",
            sa.Column("finding_id", sa.Integer(), nullable=False),
            sa.Column("part_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("finding_id", "part_id"),
        )

    if "finding_sources" not in tables:
        op.create_table(
            "finding_sources",
            sa.Column("finding_id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("finding_id", "source_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "finding_sources" in tables:
        op.drop_table("finding_sources")
    if "finding_parts" in tables:
        op.drop_table("finding_parts")
    if "findings" in tables:
        op.drop_index("ix_findings_project_id", table_name="findings")
        op.drop_table("findings")
