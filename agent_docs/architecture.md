# Architecture Notes

## HTTP Clients

All HTTP clients are async (httpx + asyncio) with a shared `BaseClient` (`clients/base.py`) providing:
- Rate limiting (configurable requests/sec)
- Retry with exponential backoff on 429/5xx
- Throttle via asyncio lock

### Client-specific patterns

- **NIH Reporter**: 1 req/sec rate limit, auto-pagination (500/page)
- **Europe PMC**: `asyncio.Semaphore(5)` for bounded concurrency (per-PMID lookups via `/article/MED/{pmid}`)
- **iCite**: Batch GET `/api/pubs?pmids=...`, 200 PMIDs per batch
- **OpenAlex**: Batch GET `/works?filter=ids.pmid:...`, 50 PMIDs per batch, cursor pagination, `OPENALEX_API_KEY` env var
- **GitHub**: `tenacity` retry logic (separate from base client) with exponential backoff on 403/429/5xx; gracefully skips topics that fail after retries

## Models

- Pydantic models define key fields explicitly but use `extra="allow"` for forward compatibility
- All API response fields are captured in JSONL even if not explicitly modeled

## Pipeline

10-step orchestrator (`pipeline/orchestrator.py`):
1. Fetch project records from NIH Reporter
2. Fetch publication links from NIH Reporter
3. Extract unique PMIDs from publication links
4. Fetch publication metadata from Europe PMC
5. Fetch iCite citation metrics for grant-associated publications
6. Build citation links (cited_pmid <-> citing_pmid) from iCite `cited_by` fields
7. Fetch iCite metrics for citing publications
8. Fetch OpenAlex works for grant-associated publications
9. Fetch OpenAlex works for citing publications
10. Search GitHub repos by core project ID topics

## Output

JSONL files written to `output/` (gitignored):
- `projects.jsonl` — NIH Reporter project records
- `publication_links.jsonl` — core_project_num <-> pmid associations (join table)
- `publications.jsonl` — Europe PMC publication metadata
- `icite.jsonl` — iCite citation metrics for grant-associated publications
- `citation_links.jsonl` — cited_pmid <-> citing_pmid mappings
- `citing_icite.jsonl` — iCite metrics for citing publications
- `openalex.jsonl` — OpenAlex work records for grant-associated publications
- `citing_openalex.jsonl` — OpenAlex work records for citing publications
- `github_core.jsonl` — GitHub repos tagged with core project ID topics

DuckDB views over these files: `icc-data-views.sql`
