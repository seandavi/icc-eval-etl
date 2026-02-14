# Package Structure

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

## Entry Point

- `main.py` — Typer CLI, loads `.env` via python-dotenv
- Config: `collection.yaml` with `core_project_identifiers` dict
- Output: `output/` directory (gitignored)
- DuckDB views: `icc-data-views.sql`
