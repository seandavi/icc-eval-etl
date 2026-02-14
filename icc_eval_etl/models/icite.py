from pydantic import BaseModel, ConfigDict


class ICiteRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    pmid: int | None = None
    title: str | None = None
    doi: str | None = None
    year: int | None = None
    citation_count: int | None = None
    citations_per_year: float | None = None
    relative_citation_ratio: float | None = None
    expected_citations_per_year: float | None = None
    field_citation_rate: float | None = None
    nih_percentile: float | None = None
    is_research_article: bool | None = None
    is_clinical: bool | None = None
    provisional: bool | None = None


class ICiteResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    data: list[ICiteRecord] = []
