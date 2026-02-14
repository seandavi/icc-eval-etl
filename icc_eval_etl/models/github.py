from pydantic import BaseModel, ConfigDict


class GitHubRepo(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    name: str
    full_name: str
    html_url: str
    description: str | None = None
    topics: list[str] = []
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None
    license: dict | None = None
    # Populated by us, not from API:
    core_project_ids: list[str] = []
