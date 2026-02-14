# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ETL pipeline for gathering NIH grant evaluation data. Given a set of NIH core project identifiers (in `collection.yaml`), the pipeline:

1. Fetches grant records from NIH Reporter API
2. Uses associated PMIDs to fetch publication records from Europe PMC API
3. Uses associated PMIDs to fetch iCite citation metrics
4. Extracts `cited_by` PMIDs from iCite records and fetches iCite metrics for citing publications
5. Fetches OpenAlex work records for both grant-associated and citing publications
6. Searches GitHub for repositories tagged with core project IDs as topics

All output is stored as JSONL, maintaining association back to core project identifiers.

## Development Setup

- Python 3.14, managed via `uv` (see `.python-version`)
- `uv sync` to install dependencies
- `uv run python main.py` to run the entrypoint
- `uv run python main.py -v` for verbose/debug logging
- Environment variables loaded from `.env` via python-dotenv (see `.env` for available vars)

## Package Structure

```
icc_eval_etl/
├── config.py                # YAML config loader
├── clients/
│   ├── base.py              # Async base client: rate limiting, retries, throttle
│   ├── nih_reporter.py      # POST /v2/projects/search + /v2/publications/search
│   ├── europepmc.py         # GET /article/MED/{pmid} (per-PMID with semaphore)
│   ├── icite.py             # GET /api/pubs?pmids=... (batch up to 200)
│   ├── openalex.py          # GET /works?filter=ids.pmid:... (batch up to 50, cursor pagination)
│   └── github.py            # GET /search/repositories (topic search, tenacity retry)
├── models/
│   ├── config.py            # CollectionConfig pydantic model
│   ├── nih_reporter.py      # Request + response models (extra="allow")
│   ├── europepmc.py         # EuropePMCResult + EuropePMCArticleResponse
│   ├── icite.py             # ICiteRecord, ICiteResponse, CitationLink
│   ├── openalex.py          # OpenAlexWork, OpenAlexResponse
│   └── github.py            # GitHubRepo
└── pipeline/
    ├── orchestrator.py      # 10-step ETL pipeline
    └── writers.py           # JSONLWriter for JSONL output
```

## Pipeline Steps (orchestrator.py)

1. Fetch project records from NIH Reporter
2. Fetch publication links from NIH Reporter
3. Extract unique PMIDs from publication links
4. Fetch publication metadata from Europe PMC
5. Fetch iCite citation metrics for grant-associated publications
6. Build citation links (cited_pmid ↔ citing_pmid) from iCite `cited_by` fields
7. Fetch iCite metrics for citing publications
8. Fetch OpenAlex works for grant-associated publications
9. Fetch OpenAlex works for citing publications
10. Search GitHub repos by core project ID topics

## Output

JSONL files are written to `output/` (gitignored):
- `projects.jsonl` — NIH Reporter project records
- `publication_links.jsonl` — core_project_num ↔ pmid associations (join table)
- `publications.jsonl` — Europe PMC publication metadata
- `icite.jsonl` — iCite citation metrics for grant-associated publications
- `citation_links.jsonl` — cited_pmid ↔ citing_pmid mappings
- `citing_icite.jsonl` — iCite metrics for citing publications
- `openalex.jsonl` — OpenAlex work records for grant-associated publications
- `citing_openalex.jsonl` — OpenAlex work records for citing publications
- `github_core.jsonl` — GitHub repos tagged with core project ID topics

DuckDB views over these files are defined in `icc-data-views.sql`:
```bash
duckdb -init icc-data-views.sql
```

## API Quirks

These are hard-won lessons — do not change without verifying against live APIs:

- **NIH Reporter projects search**: Use `project_nums` (not `core_project_nums`) in criteria. The `core_project_nums` field is silently ignored and returns ALL projects.
- **NIH Reporter publications search**: Uses `core_project_nums` correctly (opposite of projects).
- **Europe PMC**: Use the direct article endpoint `/article/MED/{pmid}` rather than the search endpoint. The search endpoint requires `src:MED` qualifier or returns 0 hits.
- **iCite**: GET `/api/pubs?pmids=...` — batch size limited to 200 PMIDs per request to avoid HTTP 414 URI Too Long errors. The `cited_by` field can be `null` (not just empty list).
- **GitHub**: Search API is rate-limited to 30 req/min (authenticated) or 10 req/min (unauthenticated). Set `GITHUB_TOKEN` in `.env` for higher limits. Topics are always lowercase.
- **OpenAlex**: Filter `ids.pmid` supports up to 100 pipe-separated values. Uses cursor pagination. Requires API key (`OPENALEX_API_KEY` in `.env`) — without it, limited to 100 requests/day. Per-page max is 200.
- **All models use `extra="allow"`** to capture full API responses without breaking on new fields.

## Architecture Notes

- All HTTP clients are async (httpx + asyncio) with shared base client providing rate limiting and retry with exponential backoff
- Europe PMC uses `asyncio.Semaphore(5)` for bounded concurrency since it's per-PMID lookups
- NIH Reporter has 1 req/sec rate limit with auto-pagination (500/page)
- GitHub client uses `tenacity` for retry logic (separate from base client) with exponential backoff on 403/429/5xx; gracefully skips topics that fail after retries
- OpenAlex client batches 50 PMIDs per request with cursor pagination; uses base client retry/throttle
- Pydantic models define key fields explicitly but allow extras for forward compatibility
- `.env` loaded at startup via python-dotenv in `main.py`
