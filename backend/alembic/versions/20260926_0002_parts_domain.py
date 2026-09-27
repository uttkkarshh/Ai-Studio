"""Add Part domain and preserved Project input fields.

Revision ID: 20260926_0002
Revises: 20260923_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260926_0002"
down_revision = "20260923_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "projects" in tables:
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        for column_name in ("objective", "initial_input", "initial_script"):
            if column_name not in project_columns:
                op.add_column("projects", sa.Column(column_name, sa.Text(), nullable=True))

    if "parts" not in tables:
        op.create_table(
            "parts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("objective", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_parts_project_id", "parts", ["project_id"], unique=False)

    if "part_sources" not in tables:
        op.create_table(
            "part_sources",
            sa.Column("part_id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("part_id", "source_id"),
        )

    if "part_relationships" not in tables:
        op.create_table(
            "part_relationships",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("from_part_id", sa.Integer(), nullable=False),
            sa.Column("to_part_id", sa.Integer(), nullable=False),
            sa.Column("relationship_type", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["from_part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("from_part_id", "to_part_id", "relationship_type"),
        )
        op.create_index(
            "ix_part_relationships_from_part_id",
            "part_relationships",
            ["from_part_id"],
            unique=False,
        )
        op.create_index(
            "ix_part_relationships_to_part_id",
            "part_relationships",
            ["to_part_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "part_relationships" in tables:
        op.drop_index("ix_part_relationships_to_part_id", table_name="part_relationships")
        op.drop_index("ix_part_relationships_from_part_id", table_name="part_relationships")
        op.drop_table("part_relationships")
    if "part_sources" in tables:
        op.drop_table("part_sources")
    if "parts" in tables:
        op.drop_index("ix_parts_project_id", table_name="parts")
        op.drop_table("parts")

    if "projects" in tables:
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        removable = [
            column_name
            for column_name in ("objective", "initial_input", "initial_script")
            if column_name in project_columns
        ]
        if removable:
            with op.batch_alter_table("projects") as batch_op:
                for column_name in removable:
                    batch_op.drop_column(column_name)