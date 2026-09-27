"""Create the initial AI Studio schema.

Revision ID: 20260923_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260923_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "projects" not in inspector.get_table_names():
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "sources" not in inspector.get_table_names():
        op.create_table(
            "sources",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("url", sa.String(length=2048), nullable=True),
            sa.Column("source_type", sa.String(length=100), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sources_project_id", "sources", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if "sources" in sa.inspect(bind).get_table_names():
        op.drop_index("ix_sources_project_id", table_name="sources")
        op.drop_table("sources")
