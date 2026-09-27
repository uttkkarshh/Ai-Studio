from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PartCreate(BaseModel):
    title: str
    objective: str | None = None
    description: str | None = None
    status: str = "planned"
    position: int = 0


class PartUpdate(BaseModel):
    title: str | None = None
    objective: str | None = None
    description: str | None = None
    status: str | None = None
    position: int | None = None


class PartCommitCreate(BaseModel):
    commit_message: str = Field(..., min_length=1)
    script_revision_id: int | None = None


class HistoricalSourceAssociation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision_id: int
    source_id: int


class HistoricalAssetAssociation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision_id: int
    asset_id: int


class PartRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    revision_number: int
    title: str
    objective: str | None
    description: str | None
    status: str
    position: int
    commit_message: str
    created_at: datetime
    created_by: str
    script_revision_id: int | None
    sources: list[int]
    assets: list[int]


class PartRevisionDetailResponse(PartRevisionResponse):
    pass


class PartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    objective: str | None
    description: str | None
    status: str
    position: int
    created_at: datetime
    updated_at: datetime