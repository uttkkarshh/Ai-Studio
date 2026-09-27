"""Add minimal project Assets and optional Part associations.

Revision ID: 20260926_0003
Revises: 20260926_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260926_0003"
down_revision = "20260926_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "assets" not in tables:
        op.create_table(
            "assets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("asset_type", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_assets_project_id", "assets", ["project_id"], unique=False)

    if "part_assets" not in tables:
        op.create_table(
            "part_assets",
            sa.Column("part_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("part_id", "asset_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "part_assets" in tables:
        op.drop_table("part_assets")
    if "assets" in tables:
        op.drop_index("ix_assets_project_id", table_name="assets")
        op.drop_table("assets")