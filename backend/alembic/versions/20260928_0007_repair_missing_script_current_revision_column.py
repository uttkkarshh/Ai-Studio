"""Repair missing script current revision column

Revision ID: 20260929_0007
Revises: 20260929_0006
Create Date: 2026-09-28 21:29:01.090184
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260929_0007"
down_revision: Union[str, Sequence[str], None] = "20260929_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    script_columns = {
        column["name"]
        for column in inspector.get_columns("scripts")
    }

    if "current_revision_id" not in script_columns:
        op.add_column(
            "scripts",
            sa.Column(
                "current_revision_id",
                sa.Integer(),
                nullable=True,
            ),
        )

        op.create_index(
            "ix_scripts_current_revision_id",
            "scripts",
            ["current_revision_id"],
            unique=False,
        )

        op.create_foreign_key(
            "fk_scripts_current_revision_id_script_revisions",
            "scripts",
            "script_revisions",
            ["current_revision_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    script_columns = {
        column["name"]
        for column in inspector.get_columns("scripts")
    }

    if "current_revision_id" in script_columns:
        op.drop_constraint(
            "fk_scripts_current_revision_id_script_revisions",
            "scripts",
            type_="foreignkey",
        )

        op.drop_index(
            "ix_scripts_current_revision_id",
            table_name="scripts",
        )

        op.drop_column(
            "scripts",
            "current_revision_id",
        )