import asyncio
import logging

from icc_eval_etl.clients.base import BaseClient
from icc_eval_etl.models.europepmc import EuropePMCArticleResponse, EuropePMCResult

logger = logging.getLogger(__name__)

EUROPEPMC_BASE = "https://www.ebi.ac.uk"


class EuropePMCClient(BaseClient):
    def __init__(self, concurrency: int = 5, **kwargs):
        super().__init__(base_url=EUROPEPMC_BASE, rate_limit=10.0, **kwargs)
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _fetch_one(self, pmid: int) -> EuropePMCResult | None:
        async with self._semaphore:
            response = await self._request(
                "GET",
                f"/europepmc/webservices/rest/article/MED/{pmid}",
                params={"format": "json", "resultType": "core"},
            )
            parsed = EuropePMCArticleResponse.model_validate(response.json())
            if parsed.result:
                return parsed.result
            logger.warning("No Europe PMC result for PMID %d", pmid)
            return None

    async def fetch_publications(
        self, pmids: list[int]
    ) -> list[EuropePMCResult]:
        logger.info("Fetching %d publications from Europe PMC", len(pmids))
        tasks = [self._fetch_one(pmid) for pmid in pmids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        publications: list[EuropePMCResult] = []
        for pmid, result in zip(pmids, results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch PMID %d from Europe PMC: %s", pmid, result)
            elif result is not None:
                publications.append(result)

        logger.info("Successfully fetched %d/%d publications", len(publications), len(pmids))
        return publications
