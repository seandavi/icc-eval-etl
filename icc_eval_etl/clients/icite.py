import logging

from icc_eval_etl.clients.base import BaseClient
from icc_eval_etl.models.icite import ICiteRecord, ICiteResponse

logger = logging.getLogger(__name__)

ICITE_BASE = "https://icite.od.nih.gov"
BATCH_SIZE = 200


class ICiteClient(BaseClient):
    def __init__(self, **kwargs):
        super().__init__(base_url=ICITE_BASE, rate_limit=5.0, **kwargs)

    async def fetch_metrics(self, pmids: list[int]) -> list[ICiteRecord]:
        all_results: list[ICiteRecord] = []

        for i in range(0, len(pmids), BATCH_SIZE):
            batch = pmids[i : i + BATCH_SIZE]
            pmid_str = ",".join(str(p) for p in batch)
            response = await self._request(
                "GET",
                "/api/pubs",
                params={"pmids": pmid_str, "format": "json"},
            )
            parsed = ICiteResponse.model_validate(response.json())
            all_results.extend(parsed.data)
            logger.info(
                "iCite: fetched %d/%d (batch %d-%d)",
                len(all_results), len(pmids), i, min(i + BATCH_SIZE, len(pmids)),
            )

        return all_results
