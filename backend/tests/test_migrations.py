import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_parts_migration_preserves_existing_project_and_source_data():
    engine = sa.create_engine("sqlite://")
    old_schema = sa.MetaData()
    projects = sa.Table(
        "projects",
        old_schema,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    sources = sa.Table(
        "sources",
        old_schema,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048)),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    old_schema.create_all(engine)

    with engine.begin() as connection:
        timestamp = sa.func.current_timestamp()
        connection.execute(
            projects.insert().values(
                id=41,
                name="Existing project",
                description="Preserved description",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        connection.execute(
            sources.insert().values(
                id=73,
                project_id=41,
                title="Existing source",
                source_type="research",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )

        migration_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for filename in (
                "20260926_0002_parts_domain.py",
                "20260926_0003_asset_part_links.py",
            ):
                migration_path = migration_dir / filename
                spec = importlib.util.spec_from_file_location(filename, migration_path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                migration.upgrade()

        inspector = sa.inspect(connection)
        assert {"parts", "part_sources", "part_relationships", "assets", "part_assets"}.issubset(
            inspector.get_table_names()
        )
        assert {"objective", "initial_input", "initial_script"}.issubset(
            {column["name"] for column in inspector.get_columns("projects")}
        )
        assert connection.execute(sa.select(projects.c.name)).scalar_one() == "Existing project"
        assert connection.execute(sa.select(sources.c.title)).scalar_one() == "Existing source"

    engine.dispose()