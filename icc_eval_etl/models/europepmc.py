from pydantic import BaseModel, ConfigDict


class EuropePMCResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    authorString: str | None = None
    pubYear: str | None = None
    abstractText: str | None = None
    citedByCount: int | None = None
    isOpenAccess: str | None = None


class EuropePMCArticleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    hitCount: int = 0
    result: EuropePMCResult | None = None
