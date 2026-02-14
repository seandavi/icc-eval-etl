from pydantic import BaseModel, ConfigDict


class ProjectSearchCriteria(BaseModel):
    project_nums: list[str]


class ProjectSearchRequest(BaseModel):
    criteria: ProjectSearchCriteria
    offset: int = 0
    limit: int = 500


class PublicationSearchCriteria(BaseModel):
    core_project_nums: list[str]


class PublicationSearchRequest(BaseModel):
    criteria: PublicationSearchCriteria
    offset: int = 0
    limit: int = 500


class SearchMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    total: int
    offset: int
    limit: int


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    appl_id: int | None = None
    project_num: str | None = None
    core_project_num: str | None = None
    project_title: str | None = None
    fiscal_year: int | None = None
    award_amount: int | None = None


class ProjectSearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    meta: SearchMeta
    results: list[ProjectRecord]


class PublicationLinkRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    coreproject: str | None = None
    pmid: int | None = None
    applid: int | None = None


class PublicationSearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    meta: SearchMeta
    results: list[PublicationLinkRecord]
