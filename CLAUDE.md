# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ETL pipeline for gathering NIH grant evaluation data. Given a set of NIH core project identifiers (in `collection.yaml`), the pipeline:

1. Fetches grant records from NIH Reporter API
2. Uses associated PMIDs to fetch publication records from Europe PMC API
3. Uses associated PMIDs to fetch iCite citation metrics
4. Extracts `cited_by` PMIDs from iCite records and fetches iCite metrics for citing publications

All output is stored as JSONL, maintaining association back to core project identifiers.

## Development Setup

- Python 3.14, managed via `uv` (see `.python-version`)
- `uv sync` to install dependencies
- `uv run python main.py` to run the entrypoint
- `uv run python main.py -v` for verbose/debug logging

## Package Structure

```
icc_eval_etl/
├── config.py                # YAML config loader
├── clients/
│   ├── base.py              # Async base client: rate limiting, retries, throttle
│   ├── nih_reporter.py      # POST /v2/projects/search + /v2/publications/search
│   ├── europepmc.py         # GET /article/MED/{pmid} (per-PMID with semaphore)
│   └── icite.py             # GET /api/pubs?pmids=... (batch up to 200)
├── models/
│   ├── config.py            # CollectionConfig pydantic model
│   ├── nih_reporter.py      # Request + response models (extra="allow")
│   ├── europepmc.py         # EuropePMCResult + EuropePMCArticleResponse
│   └── icite.py             # ICiteRecord, ICiteResponse, CitationLink
└── pipeline/
    ├── orchestrator.py      # 7-step ETL pipeline
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

## Output

JSONL files are written to `output/` (gitignored):
- `projects.jsonl` — NIH Reporter project records
- `publication_links.jsonl` — core_project_num ↔ pmid associations (join table)
- `publications.jsonl` — Europe PMC publication metadata
- `icite.jsonl` — iCite citation metrics for grant-associated publications
- `citation_links.jsonl` — cited_pmid ↔ citing_pmid mappings
- `citing_icite.jsonl` — iCite metrics for citing publications

## API Quirks

These are hard-won lessons — do not change without verifying against live APIs:

- **NIH Reporter projects search**: Use `project_nums` (not `core_project_nums`) in criteria. The `core_project_nums` field is silently ignored and returns ALL projects.
- **NIH Reporter publications search**: Uses `core_project_nums` correctly (opposite of projects).
- **Europe PMC**: Use the direct article endpoint `/article/MED/{pmid}` rather than the search endpoint. The search endpoint requires `src:MED` qualifier or returns 0 hits.
- **iCite**: GET `/api/pubs?pmids=...` — batch size limited to 200 PMIDs per request to avoid HTTP 414 URI Too Long errors. The `cited_by` field can be `null` (not just empty list).
- **All models use `extra="allow"`** to capture full API responses without breaking on new fields.

## Architecture Notes

- All HTTP clients are async (httpx + asyncio) with shared base client providing rate limiting and retry with exponential backoff
- Europe PMC uses `asyncio.Semaphore(5)` for bounded concurrency since it's per-PMID lookups
- NIH Reporter has 1 req/sec rate limit with auto-pagination (500/page)
- Pydantic models define key fields explicitly but allow extras for forward compatibility
