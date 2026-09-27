"""Add Script, ScriptDraft, ScriptRevision and wire PartRevision to a specific ScriptRevision.

Revision ID: 20260928_0005
Revises: 20260927_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260928_0005"
down_revision = "20260927_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "script_drafts" not in tables:
        op.create_table(
            "script_drafts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("part_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("content", sa.JSON(), nullable=True),
            sa.Column("created_by_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_script_drafts_part_id", "script_drafts", ["part_id"], unique=False)

    if "scripts" not in tables:
        op.create_table(
            "scripts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("part_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("part_id", name="uq_scripts_part_id"),
        )
        op.create_index("ix_scripts_part_id", "scripts", ["part_id"], unique=False)

    if "script_revisions" not in tables:
        op.create_table(
            "script_revisions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("script_id", sa.Integer(), nullable=False),
            sa.Column("revision_number", sa.Integer(), nullable=False),
            sa.Column("content", sa.JSON(), nullable=True),
            sa.Column("created_by_type", sa.String(length=50), nullable=False),
            sa.Column("commit_message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("source_draft_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["script_id"], ["scripts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_draft_id"], ["script_drafts.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("script_id", "revision_number", name="uq_script_revisions_script_revision_number"),
        )
        op.create_index("ix_script_revisions_script_id", "script_revisions", ["script_id"], unique=False)
        op.create_index("ix_script_revisions_source_draft_id", "script_revisions", ["source_draft_id"], unique=False)

    if "scripts" in tables and "current_revision_id" not in {c["name"] for c in inspector.get_columns("scripts")}:
        op.add_column("scripts", sa.Column("current_revision_id", sa.Integer(), nullable=True))
        op.create_index("ix_scripts_current_revision_id", "scripts", ["current_revision_id"], unique=False)
        op.create_foreign_key(
            "fk_scripts_current_revision_id_script_revisions",
            "scripts",
            "script_revisions",
            ["current_revision_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "part_revisions" in tables:
        part_revision_columns = {column["name"] for column in inspector.get_columns("part_revisions")}
        if "script_revision_id" not in part_revision_columns:
            op.add_column(
                "part_revisions",
                sa.Column("script_revision_id", sa.Integer(), nullable=True),
            )
            op.create_index(
                "ix_part_revisions_script_revision_id",
                "part_revisions",
                ["script_revision_id"],
                unique=False,
            )
            op.create_foreign_key(
                "fk_part_revisions_script_revision_id_script_revisions",
                "part_revisions",
                "script_revisions",
                ["script_revision_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "part_revisions" in tables:
        part_revision_columns = {column["name"] for column in inspector.get_columns("part_revisions")}
        if "script_revision_id" in part_revision_columns:
            op.drop_constraint(
                "fk_part_revisions_script_revision_id_script_revisions",
                "part_revisions",
                type_="foreignkey",
            )
            op.drop_index("ix_part_revisions_script_revision_id", table_name="part_revisions")
            op.drop_column("part_revisions", "script_revision_id")

    if "script_revisions" in tables:
        op.drop_index("ix_script_revisions_source_draft_id", table_name="script_revisions")
        op.drop_index("ix_script_revisions_script_id", table_name="script_revisions")
        op.drop_table("script_revisions")
    if "script_drafts" in tables:
        op.drop_index("ix_script_drafts_part_id", table_name="script_drafts")
        op.drop_table("script_drafts")
    if "scripts" in tables:
        op.drop_index("ix_scripts_current_revision_id", table_name="scripts")
        op.drop_index("ix_scripts_part_id", table_name="scripts")
        op.drop_table("scripts")
