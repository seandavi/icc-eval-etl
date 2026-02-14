from pydantic import BaseModel, ConfigDict


class OpenAlexWork(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    doi: str | None = None
    title: str | None = None
    display_name: str | None = None
    publication_year: int | None = None
    publication_date: str | None = None
    ids: dict | None = None
    type: str | None = None
    language: str | None = None
    primary_location: dict | None = None
    open_access: dict | None = None
    authorships: list[dict] | None = None
    cited_by_count: int | None = None
    fwci: float | None = None
    biblio: dict | None = None
    is_retracted: bool | None = None
    referenced_works_count: int | None = None
    primary_topic: dict | None = None
    topics: list[dict] | None = None
    mesh: list[dict] | None = None
    keywords: list[dict] | None = None


class OpenAlexResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    meta: dict = {}
    results: list[OpenAlexWork] = []
