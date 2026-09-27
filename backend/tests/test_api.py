import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.dependencies import get_db
from app.main import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_project_crud(client):
    initial_script = "A complete user-authored script."
    created = client.post(
        "/api/projects/",
        json={
            "name": "Test project",
            "objective": "Create a short explainer",
            "initial_input": "Keep the tone accessible.",
            "initial_script": initial_script,
        },
    )
    assert created.status_code == 201
    project = created.json()
    project_id = project["id"]
    assert project["objective"] == "Create a short explainer"
    assert project["initial_input"] == "Keep the tone accessible."
    assert project["initial_script"] == initial_script

    assert client.get("/api/projects/").status_code == 200
    assert client.get(f"/api/projects/{project_id}").json()["name"] == "Test project"
    updated = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Updated project", "description": "Details"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated project"
    updated = client.put(
        f"/api/projects/{project_id}",
        json={"objective": "Revised objective", "initial_script": initial_script},
    )
    assert updated.json()["objective"] == "Revised objective"
    assert updated.json()["initial_script"] == initial_script
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_nonexistent_project_returns_404(client):
    assert client.get("/api/projects/999999").status_code == 404
    assert client.put("/api/projects/999999", json={"name": "Missing"}).status_code == 404
    assert client.delete("/api/projects/999999").status_code == 404


def test_parts_crud_arbitrary_count_and_project_ownership(client):
    project_id = client.post("/api/projects/", json={"name": "Parts"}).json()["id"]
    other_project_id = client.post("/api/projects/", json={"name": "Other"}).json()["id"]

    created_parts = []
    for index in range(10):
        response = client.post(
            f"/api/projects/{project_id}/parts/",
            json={"title": f"Part {index}", "position": index},
        )
        assert response.status_code == 201
        created_parts.append(response.json())

    part_id = created_parts[0]["id"]
    assert len(client.get(f"/api/projects/{project_id}/parts/").json()) == 10
    assert all(part["project_id"] == project_id for part in created_parts)
    assert client.get(f"/api/projects/{project_id}/parts/{part_id}").status_code == 200

    updated = client.put(
        f"/api/projects/{project_id}/parts/{part_id}",
        json={"title": "Updated Part", "status": "in_review", "position": 11},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_review"
    assert updated.json()["position"] == 11

    assert client.get(f"/api/projects/{other_project_id}/parts/{part_id}").status_code == 404
    assert client.put(
        f"/api/projects/{other_project_id}/parts/{part_id}", json={"title": "Wrong project"}
    ).status_code == 404
    assert client.delete(f"/api/projects/{project_id}/parts/{part_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}/parts/{part_id}").status_code == 404


def test_source_crud_and_project_validation(client):
    project_id = client.post("/api/projects/", json={"name": "Sources"}).json()["id"]
    payload = {
        "title": "FastAPI docs",
        "url": "https://fastapi.tiangolo.com",
        "source_type": "documentation",
        "content": "FastAPI content",
        "metadata": {"section": "intro"},
    }
    created = client.post(f"/api/projects/{project_id}/sources/", json=payload)
    assert created.status_code == 201
    source = created.json()
    source_id = source["id"]
    assert source["metadata"] == payload["metadata"]
    assert source["part_ids"] == []
    assert len(client.get(f"/api/projects/{project_id}/sources/").json()) == 1
    assert client.get(f"/api/projects/{project_id}/sources/{source_id}").status_code == 200

    updated = client.put(
        f"/api/projects/{project_id}/sources/{source_id}",
        json={"title": "Updated docs"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated docs"
    assert client.delete(f"/api/projects/{project_id}/sources/{source_id}").status_code == 204

    assert client.get("/api/projects/999999/sources/").status_code == 404
    assert client.post("/api/projects/999999/sources/", json=payload).status_code == 404


def test_project_source_can_be_shared_by_multiple_parts(client):
    project_id = client.post("/api/projects/", json={"name": "Shared source"}).json()["id"]
    other_project_id = client.post("/api/projects/", json={"name": "Other"}).json()["id"]
    part_ids = [
        client.post(
            f"/api/projects/{project_id}/parts/", json={"title": f"Part {number}"}
        ).json()["id"]
        for number in range(2)
    ]
    foreign_part_id = client.post(
        f"/api/projects/{other_project_id}/parts/", json={"title": "Foreign part"}
    ).json()["id"]
    payload = {
        "title": "Shared research",
        "source_type": "research",
        "part_ids": part_ids,
    }

    created = client.post(f"/api/projects/{project_id}/sources/", json=payload)
    assert created.status_code == 201
    source_id = created.json()["id"]
    assert created.json()["project_id"] == project_id
    assert set(created.json()["part_ids"]) == set(part_ids)

    updated = client.put(
        f"/api/projects/{project_id}/sources/{source_id}",
        json={"part_ids": [part_ids[1]]},
    )
    assert updated.status_code == 200
    assert updated.json()["part_ids"] == [part_ids[1]]

    invalid = {**payload, "part_ids": [foreign_part_id]}
    assert client.post(f"/api/projects/{project_id}/sources/", json=invalid).status_code == 422


def test_project_asset_can_be_shared_by_multiple_parts(db_session):
    from app.models import Asset, Part, Project

    project = Project(name="Shared asset")
    parts = [Part(title="Part A", project=project), Part(title="Part B", project=project)]
    asset = Asset(name="Storyboard image", asset_type="image", project=project, parts=parts)
    db_session.add(asset)
    db_session.commit()

    assert asset.project_id == project.id
    assert {part.id for part in asset.parts} == {part.id for part in parts}


def test_finding_crud_and_status_validation(client):
    project_id = client.post("/api/projects/", json={"name": "Finding project"}).json()["id"]
    source_id = client.post(
        f"/api/projects/{project_id}/sources/",
        json={
            "title": "Finding source",
            "source_type": "research",
            "content": "Source content",
        },
    ).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Finding part", "objective": "Use this finding"},
    ).json()["id"]

    created = client.post(
        f"/api/projects/{project_id}/findings",
        json={
            "heading": "Domestic production was insufficient",
            "content": {"text": "Production could not meet demand."},
            "created_by_type": "ai",
            "part_ids": [part_id],
            "source_ids": [source_id],
        },
    )
    assert created.status_code == 201
    finding = created.json()
    assert finding["project_id"] == project_id
    assert finding["heading"] == "Domestic production was insufficient"
    assert set(finding["part_ids"]) == {part_id}
    assert set(finding["source_ids"]) == {source_id}

    listed = client.get(f"/api/projects/{project_id}/findings")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/findings/{finding['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["content"]["text"] == "Production could not meet demand."

    updated = client.put(
        f"/api/findings/{finding['id']}",
        json={"heading": "Updated finding", "status": "archived"},
    )
    assert updated.status_code == 200
    assert updated.json()["heading"] == "Updated finding"
    assert updated.json()["status"] == "archived"

    bad_created_by = client.post(
        f"/api/projects/{project_id}/findings",
        json={
            "heading": "Bad creator",
            "content": {"text": "x"},
            "created_by_type": "invalid",
        },
    )
    assert bad_created_by.status_code == 422

    bad_status = client.put(
        f"/api/findings/{finding['id']}",
        json={"status": "invalid"},
    )
    assert bad_status.status_code == 422

    deleted = client.delete(f"/api/findings/{finding['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/findings/{finding['id']}").status_code == 404


def test_finding_links_same_project_parts_and_sources(client):
    project_id = client.post("/api/projects/", json={"name": "Finding links"}).json()["id"]
    part_a = client.post(f"/api/projects/{project_id}/parts/", json={"title": "Part A"}).json()["id"]
    part_b = client.post(f"/api/projects/{project_id}/parts/", json={"title": "Part B"}).json()["id"]
    source_a = client.post(
        f"/api/projects/{project_id}/sources/",
        json={"title": "Source A", "source_type": "research"},
    ).json()["id"]
    source_b = client.post(
        f"/api/projects/{project_id}/sources/",
        json={"title": "Source B", "source_type": "research"},
    ).json()["id"]

    created = client.post(
        f"/api/projects/{project_id}/findings",
        json={
            "heading": "Shared finding",
            "content": {"text": "Useful to multiple parts."},
            "created_by_type": "user",
            "part_ids": [part_a, part_b],
            "source_ids": [source_a, source_b],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert set(body["part_ids"]) == {part_a, part_b}
    assert set(body["source_ids"]) == {source_a, source_b}

    part_result = client.get(f"/api/findings/{body['id']}")
    assert part_result.status_code == 200
    assert set(part_result.json()["part_ids"]) == {part_a, part_b}


def test_finding_rejects_cross_project_links(client):
    project_a = client.post("/api/projects/", json={"name": "Project A"}).json()["id"]
    project_b = client.post("/api/projects/", json={"name": "Project B"}).json()["id"]
    part_b = client.post(f"/api/projects/{project_b}/parts/", json={"title": "Wrong project part"}).json()["id"]
    source_b = client.post(
        f"/api/projects/{project_b}/sources/",
        json={"title": "Wrong project source", "source_type": "research"},
    ).json()["id"]
    finding = client.post(
        f"/api/projects/{project_a}/findings",
        json={
            "heading": "Cross project test",
            "content": {"text": "Should fail"},
            "created_by_type": "imported",
        },
    )
    assert finding.status_code == 201

    bad_part = client.put(
        f"/api/findings/{finding.json()['id']}",
        json={"part_ids": [part_b]},
    )
    assert bad_part.status_code == 422

    bad_source = client.put(
        f"/api/findings/{finding.json()['id']}",
        json={"source_ids": [source_b]},
    )
    assert bad_source.status_code == 422


def test_finding_delete_and_project_cascade(client, db_session):
    from app.models import Finding, Project

    project = Project(name="Cascade project")
    db_session.add(project)
    db_session.commit()

    part = project.parts.__class__
    part_id = client.post(f"/api/projects/{project.id}/parts/", json={"title": "Cascade part"}).json()["id"]
    source_id = client.post(
        f"/api/projects/{project.id}/sources/",
        json={"title": "Cascade source", "source_type": "research"},
    ).json()["id"]

    finding = client.post(
        f"/api/projects/{project.id}/findings",
        json={
            "heading": "Cascade finding",
            "content": {"text": "To be removed"},
            "created_by_type": "user",
            "part_ids": [part_id],
            "source_ids": [source_id],
        },
    )
    finding_id = finding.json()["id"]

    assert client.delete(f"/api/findings/{finding_id}").status_code == 204
    assert db_session.query(Finding).filter(Finding.id == finding_id).count() == 0

    project_id = project.id
    client.delete(f"/api/projects/{project_id}")
    assert db_session.query(Finding).filter(Finding.project_id == project_id).count() == 0


def test_script_draft_accept_creates_script_and_revision(client, db_session):
    project_id = client.post("/api/projects/", json={"name": "Script project"}).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Script part", "objective": "Explain the script"},
    ).json()["id"]

    draft_response = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={
            "title": "Draft 1",
            "content": {"sections": [{"type": "narration", "content": "Intro"}]},
            "created_by_type": "ai",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["part_id"] == part_id
    assert draft["status"] == "active"

    get_drafts = client.get(f"/api/parts/{part_id}/script-drafts")
    assert get_drafts.status_code == 200
    assert len(get_drafts.json()) == 1

    accept = client.post(f"/api/script-drafts/{draft['id']}/accept")
    assert accept.status_code == 200
    accepted = accept.json()
    assert accepted["status"] == "accepted"

    part_script = client.get(f"/api/parts/{part_id}/script")
    assert part_script.status_code == 200
    script = part_script.json()
    assert script["part_id"] == part_id
    assert script["current_revision_id"] is not None

    revisions = client.get(f"/api/scripts/{script['id']}/revisions")
    assert revisions.status_code == 200
    assert [item["revision_number"] for item in revisions.json()] == [1]
    assert revisions.json()[0]["content"]["sections"][0]["content"] == "Intro"

    commit = client.post(
        f"/api/parts/{part_id}/commits",
        json={"commit_message": "Recorded script state"},
    )
    assert commit.status_code == 201
    assert commit.json()["script_revision_id"] == revisions.json()[0]["id"]


def test_script_draft_restore_and_revision_history(client):
    project_id = client.post("/api/projects/", json={"name": "Script restore"}).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Restore part"},
    ).json()["id"]

    draft1 = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={"title": "A", "content": {"text": "v1"}, "created_by_type": "user"},
    )
    assert draft1.status_code == 201
    first_accept = client.post(f"/api/script-drafts/{draft1.json()['id']}/accept")
    script_id = first_accept.json()["script_id"]

    draft2 = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={"title": "B", "content": {"text": "v2"}, "created_by_type": "ai"},
    )
    accept2 = client.post(f"/api/script-drafts/{draft2.json()['id']}/accept")
    assert accept2.status_code == 200
    revision_2 = accept2.json()["revision_number"]
    assert revision_2 == 2

    revision_list = client.get(f"/api/scripts/{script_id}/revisions")
    assert revision_list.status_code == 200
    assert [item["revision_number"] for item in revision_list.json()] == [2, 1]

    restore = client.post(
        f"/api/scripts/{script_id}/revisions/1/restore",
        json={"created_by_type": "user"},
    )
    assert restore.status_code == 200
    restored = restore.json()
    assert restored["revision_number"] == 3
    assert restored["content"] == {"text": "v1"}


def test_part_commit_accepts_script_revision_for_same_part(client):
    project_id = client.post("/api/projects/", json={"name": "Same part commit"}).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Scripted part"},
    ).json()["id"]

    draft = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={"title": "Draft 1", "content": {"text": "v1"}, "created_by_type": "user"},
    )
    assert draft.status_code == 201
    accepted = client.post(f"/api/script-drafts/{draft.json()['id']}/accept")
    assert accepted.status_code == 200
    revision_id = accepted.json()["id"]

    commit = client.post(
        f"/api/parts/{part_id}/commits",
        json={"commit_message": "Recorded approved script", "script_revision_id": revision_id},
    )
    assert commit.status_code == 201
    assert commit.json()["script_revision_id"] == revision_id


def test_part_commit_rejects_script_revision_for_other_part(client):
    project_one = client.post("/api/projects/", json={"name": "Project one"}).json()["id"]
    project_two = client.post("/api/projects/", json={"name": "Project two"}).json()["id"]
    part_one = client.post(
        f"/api/projects/{project_one}/parts/",
        json={"title": "Part one"},
    ).json()["id"]
    part_two = client.post(
        f"/api/projects/{project_two}/parts/",
        json={"title": "Part two"},
    ).json()["id"]

    draft = client.post(
        f"/api/parts/{part_one}/script-drafts",
        json={"title": "Draft", "content": {"text": "foreign"}, "created_by_type": "user"},
    )
    assert draft.status_code == 201
    accepted = client.post(f"/api/script-drafts/{draft.json()['id']}/accept")
    assert accepted.status_code == 200
    foreign_revision_id = accepted.json()["id"]

    reject = client.post(
        f"/api/parts/{part_two}/commits",
        json={"commit_message": "Wrong part script", "script_revision_id": foreign_revision_id},
    )
    assert reject.status_code == 400


def test_restore_part_revision_restores_script_and_keeps_history(client, db_session):
    from app.models import Asset, PartRevision, Source

    project_id = client.post("/api/projects/", json={"name": "Script restore history"}).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Restore tracked part", "status": "working"},
    ).json()["id"]

    source_a = Source(project_id=project_id, title="Source A", source_type="article")
    source_b = Source(project_id=project_id, title="Source B", source_type="article")
    asset_a = Asset(project_id=project_id, name="Asset A", asset_type="image")
    asset_b = Asset(project_id=project_id, name="Asset B", asset_type="image")
    db_session.add_all([source_a, source_b, asset_a, asset_b])
    db_session.commit()

    part_response = client.put(
        f"/api/projects/{project_id}/parts/{part_id}",
        json={"status": "working"},
    )
    assert part_response.status_code == 200

    from app.models import Part

    part_obj = db_session.get(Part, part_id)
    part_obj.sources = [source_a, source_b]
    part_obj.assets = [asset_a, asset_b]
    db_session.commit()

    draft_one = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={"title": "Script v1", "content": {"text": "v1"}, "created_by_type": "user"},
    )
    assert draft_one.status_code == 201
    accepted_one = client.post(f"/api/script-drafts/{draft_one.json()['id']}/accept")
    assert accepted_one.status_code == 200
    revision_one_id = accepted_one.json()["id"]

    draft_two = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={"title": "Script v2", "content": {"text": "v2"}, "created_by_type": "ai"},
    )
    assert draft_two.status_code == 201
    accepted_two = client.post(f"/api/script-drafts/{draft_two.json()['id']}/accept")
    assert accepted_two.status_code == 200
    revision_two_id = accepted_two.json()["id"]

    first_commit = client.post(
        f"/api/parts/{part_id}/commits",
        json={"commit_message": "Initial script snapshot", "script_revision_id": revision_one_id},
    )
    assert first_commit.status_code == 201
    first_commit_data = first_commit.json()
    assert set(first_commit_data["sources"]) == {source_a.id, source_b.id}
    assert set(first_commit_data["assets"]) == {asset_a.id, asset_b.id}

    second_commit = client.post(
        f"/api/parts/{part_id}/commits",
        json={"commit_message": "Later script snapshot", "script_revision_id": revision_two_id},
    )
    assert second_commit.status_code == 201

    restore = client.post(f"/api/parts/{part_id}/commits/{first_commit_data['id']}/restore")
    assert restore.status_code == 200
    restored = restore.json()
    assert restored["script_revision_id"] == revision_one_id
    assert client.get(f"/api/parts/{part_id}/script").json()["current_revision_id"] == revision_one_id
    assert client.get(f"/api/parts/{part_id}/commits/{first_commit_data['id']}").json()["script_revision_id"] == revision_one_id
    assert set(restored["sources"]) == {source_a.id, source_b.id}
    assert set(restored["assets"]) == {asset_a.id, asset_b.id}
    assert len(client.get(f"/api/parts/{part_id}/commits").json()) == 3
    assert len(client.get(f"/api/scripts/{accepted_one.json()['script_id']}/revisions").json()) == 2


def test_restore_part_revision_with_null_script_revision_clears_current_scope(client, db_session):
    from app.models import Asset, PartRevision, Source

    project_id = client.post("/api/projects/", json={"name": "Null script restore"}).json()["id"]
    part_id = client.post(
        f"/api/projects/{project_id}/parts/",
        json={"title": "Null script part"},
    ).json()["id"]

    source = Source(project_id=project_id, title="Source", source_type="article")
    asset = Asset(project_id=project_id, name="Asset", asset_type="image")
    db_session.add_all([source, asset])
    db_session.commit()

    from app.models import Part

    part = db_session.get(Part, part_id)
    part.sources = [source]
    part.assets = [asset]
    db_session.commit()

    draft = client.post(
        f"/api/parts/{part_id}/script-drafts",
        json={"title": "Script", "content": {"text": "v1"}, "created_by_type": "user"},
    )
    assert draft.status_code == 201
    accepted = client.post(f"/api/script-drafts/{draft.json()['id']}/accept")
    assert accepted.status_code == 200
    script_id = accepted.json()["script_id"]
    assert client.get(f"/api/parts/{part_id}/script").json()["current_revision_id"] is not None

    historical = PartRevision(
        part_id=part_id,
        revision_number=1,
        title="Historical title",
        objective="Historical objective",
        description="Historical description",
        status="planned",
        position=1,
        commit_message="Historical snapshot without script",
        created_by="user",
        script_revision_id=None,
    )
    historical.sources = [source]
    historical.assets = [asset]
    db_session.add(historical)
    db_session.commit()
    db_session.refresh(historical)

    restore = client.post(f"/api/parts/{part_id}/commits/{historical.id}/restore")
    assert restore.status_code == 200
    restored = restore.json()
    assert restored["script_revision_id"] is None
    assert client.get(f"/api/parts/{part_id}/script").json()["current_revision_id"] is None
    assert client.get(f"/api/parts/{part_id}/commits/{historical.id}").json()["script_revision_id"] is None
    assert set(restored["sources"]) == {source.id}
    assert set(restored["assets"]) == {asset.id}
    assert len(client.get(f"/api/scripts/{script_id}/revisions").json()) == 1


def test_part_commit_records_historical_state_and_restore(client, db_session):
    from app.models import Asset, Part, Project, Source

    project = Project(name="History project")
    db_session.add(project)
    db_session.commit()

    source_1 = Source(project_id=project.id, title="Source 1", source_type="research")
    source_2 = Source(project_id=project.id, title="Source 2", source_type="research")
    asset_1 = Asset(project_id=project.id, name="Asset 1", asset_type="image")
    asset_2 = Asset(project_id=project.id, name="Asset 2", asset_type="image")
    db_session.add_all([source_1, source_2, asset_1, asset_2])
    db_session.commit()

    part = Part(
        project_id=project.id,
        title="Original title",
        objective="Original objective",
        description="Original description",
        status="working",
        position=2,
    )
    part.sources = [source_1, source_2]
    part.assets = [asset_1, asset_2]
    db_session.add(part)
    db_session.commit()
    db_session.refresh(part)

    response = client.post(
        f"/api/parts/{part.id}/commits",
        json={"commit_message": "Initial research capture"},
    )
    assert response.status_code == 201
    revision = response.json()
    assert revision["part_id"] == part.id
    assert revision["revision_number"] == 1
    assert revision["title"] == "Original title"
    assert revision["objective"] == "Original objective"
    assert revision["status"] == "working"
    assert set(revision["sources"]) == {source_1.id, source_2.id}
    assert set(revision["assets"]) == {asset_1.id, asset_2.id}

    part.title = "Updated title"
    part.objective = "Updated objective"
    part.sources = [source_1]
    part.assets = [asset_1]
    db_session.commit()

    second = client.post(
        f"/api/parts/{part.id}/commits",
        json={"commit_message": "Trimmed stale associations"},
    )
    assert second.status_code == 201
    assert second.json()["revision_number"] == 2

    part.title = "Final title"
    part.objective = "Final objective"
    part.sources = [source_2]
    part.assets = [asset_2]
    db_session.commit()

    third = client.post(
        f"/api/parts/{part.id}/commits",
        json={"commit_message": "Final update"},
    )
    assert third.status_code == 201
    assert third.json()["revision_number"] == 3

    listed = client.get(f"/api/parts/{part.id}/commits")
    assert listed.status_code == 200
    assert [item["revision_number"] for item in listed.json()] == [3, 2, 1]

    first_revision = client.get(f"/api/parts/{part.id}/commits/{revision['id']}")
    assert first_revision.status_code == 200
    assert first_revision.json()["revision_number"] == 1
    assert first_revision.json()["sources"] == [source_1.id, source_2.id]
    assert first_revision.json()["assets"] == [asset_1.id, asset_2.id]

    restore = client.post(f"/api/parts/{part.id}/commits/{revision['id']}/restore")
    assert restore.status_code == 200
    restore_data = restore.json()
    assert restore_data["part_id"] == part.id
    assert restore_data["revision_number"] == 4
    assert restore_data["title"] == "Original title"
    assert restore_data["commit_message"] == "Restored from revision 1"
    assert set(restore_data["sources"]) == {source_1.id, source_2.id}
    assert set(restore_data["assets"]) == {asset_1.id, asset_2.id}

    current_part = client.get(f"/api/projects/{project.id}/parts/{part.id}")
    assert current_part.status_code == 200
    assert current_part.json()["title"] == "Original title"
    assert current_part.json()["objective"] == "Original objective"
    assert current_part.json()["status"] == "working"

    history = client.get(f"/api/parts/{part.id}/commits")
    assert [item["revision_number"] for item in history.json()] == [4, 3, 2, 1]

    other_project = Project(name="Other project")
    db_session.add(other_project)
    db_session.commit()
    other_part = Part(project_id=other_project.id, title="Other part")
    db_session.add(other_part)
    db_session.commit()
    invalid_restore = client.post(f"/api/parts/{other_part.id}/commits/{revision['id']}/restore")
    assert invalid_restore.status_code == 404

    db_session.delete(part)
    db_session.commit()
    assert client.get(f"/api/parts/{part.id}/commits").status_code == 404
