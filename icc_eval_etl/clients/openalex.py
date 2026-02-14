import logging
import os

from icc_eval_etl.clients.base import BaseClient
from icc_eval_etl.models.openalex import OpenAlexWork, OpenAlexResponse

logger = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"
BATCH_SIZE = 50  # max 100 pipe-separated values per filter, stay conservative


class OpenAlexClient(BaseClient):
    def __init__(self, **kwargs):
        super().__init__(base_url=OPENALEX_BASE, rate_limit=10.0, **kwargs)
        self._api_key = os.environ.get("OPENALEX_API_KEY")
        if not self._api_key:
            logger.warning(
                "OPENALEX_API_KEY not set — OpenAlex limits unauthenticated requests to 100/day"
            )

    def _base_params(self) -> dict:
        params: dict = {"per_page": "200"}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def fetch_works(self, pmids: list[int]) -> list[OpenAlexWork]:
        """Fetch OpenAlex work records for a list of PMIDs."""
        all_results: list[OpenAlexWork] = []

        for i in range(0, len(pmids), BATCH_SIZE):
            batch = pmids[i : i + BATCH_SIZE]
            pmid_filter = "|".join(str(p) for p in batch)
            params = self._base_params()
            params["filter"] = f"ids.pmid:{pmid_filter}"

            # Use cursor pagination to collect all results for this batch
            params["cursor"] = "*"
            batch_results: list[OpenAlexWork] = []

            while True:
                response = await self._request("GET", "/works", params=params)
                parsed = OpenAlexResponse.model_validate(response.json())
                batch_results.extend(parsed.results)

                next_cursor = parsed.meta.get("next_cursor")
                if not next_cursor or not parsed.results:
                    break
                params["cursor"] = next_cursor

            all_results.extend(batch_results)
            logger.info(
                "OpenAlex: fetched %d/%d PMIDs (batch %d-%d, got %d works)",
                min(i + BATCH_SIZE, len(pmids)),
                len(pmids),
                i,
                min(i + BATCH_SIZE, len(pmids)),
                len(batch_results),
            )

        return all_results
