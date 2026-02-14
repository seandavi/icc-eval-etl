import logging

from icc_eval_etl.clients.base import BaseClient
from icc_eval_etl.models.nih_reporter import (
    ProjectRecord,
    ProjectSearchCriteria,
    ProjectSearchRequest,
    ProjectSearchResponse,
    PublicationLinkRecord,
    PublicationSearchCriteria,
    PublicationSearchRequest,
    PublicationSearchResponse,
)

logger = logging.getLogger(__name__)

NIH_REPORTER_BASE = "https://api.reporter.nih.gov"


class NIHReporterClient(BaseClient):
    def __init__(self, **kwargs):
        super().__init__(base_url=NIH_REPORTER_BASE, rate_limit=1.0, **kwargs)

    async def search_projects(
        self, core_project_nums: list[str]
    ) -> list[ProjectRecord]:
        all_results: list[ProjectRecord] = []
        offset = 0
        limit = 500

        while True:
            request = ProjectSearchRequest(
                criteria=ProjectSearchCriteria(project_nums=core_project_nums),
                offset=offset,
                limit=limit,
            )
            response = await self._request(
                "POST",
                "/v2/projects/search",
                json=request.model_dump(),
            )
            parsed = ProjectSearchResponse.model_validate(response.json())
            all_results.extend(parsed.results)
            logger.info(
                "Projects: fetched %d/%d (offset=%d)",
                len(all_results), parsed.meta.total, offset,
            )
            if offset + limit >= parsed.meta.total or offset + limit > 14999:
                break
            offset += limit

        return all_results

    async def search_publications(
        self, core_project_nums: list[str]
    ) -> list[PublicationLinkRecord]:
        all_results: list[PublicationLinkRecord] = []
        offset = 0
        limit = 500

        while True:
            request = PublicationSearchRequest(
                criteria=PublicationSearchCriteria(core_project_nums=core_project_nums),
                offset=offset,
                limit=limit,
            )
            response = await self._request(
                "POST",
                "/v2/publications/search",
                json=request.model_dump(),
            )
            parsed = PublicationSearchResponse.model_validate(response.json())
            all_results.extend(parsed.results)
            logger.info(
                "Publication links: fetched %d/%d (offset=%d)",
                len(all_results), parsed.meta.total, offset,
            )
            if offset + limit >= parsed.meta.total or offset + limit > 9999:
                break
            offset += limit

        return all_results
