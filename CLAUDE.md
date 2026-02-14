# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ETL pipeline for gathering NIH grant evaluation data. Given a set of NIH core project identifiers (in `collection.yaml`), the pipeline:

1. Fetches grant records from NIH Reporter API (`https://api.reporter.nih.gov/`)
2. Uses associated PMIDs to fetch publication records from Europe PMC API (`https://europepmc.org/RestfulWebService`)
3. Uses associated PMIDs to fetch iCite citation metrics (`https://support.icite.nih.gov/hc/en-us/articles/9513563045787-Bulk-Data-and-API`)

All output is stored as JSONL, maintaining association back to core project identifiers.

## Development Setup

- Python 3.14, managed via `uv` (see `.python-version`)
- `uv sync` to install dependencies
- `uv run python main.py` to run the entrypoint

## Configuration

Grant collections are defined in `collection.yaml` with NIH core project identifiers:
```yaml
core_project_identifiers:
  u54od036472:
```

## Package Structure

```
icc_eval_etl/
├── config.py                # YAML config loader
├── clients/
│   ├── base.py              # Async base client: rate limiting, retries, throttle
│   ├── nih_reporter.py      # POST /v2/projects/search + /v2/publications/search
│   ├── europepmc.py         # GET /search?query=EXT_ID:{pmid} (per-PMID with semaphore)
│   └── icite.py             # GET /api/pubs?pmids=... (batch up to 1000)
├── models/
│   ├── config.py            # CollectionConfig pydantic model
│   ├── nih_reporter.py      # Request + response models (extra="allow")
│   ├── europepmc.py         # EuropePMCResult + response wrapper
│   └── icite.py             # ICiteRecord + response wrapper
└── pipeline/
    ├── orchestrator.py      # 5-step ETL: projects → pub links → PMIDs → epmc → icite
    └── writers.py           # JSONLWriter for JSONL output
```

## Output

JSONL files are written to `output/` (gitignored):
- `projects.jsonl` — NIH Reporter project records
- `publication_links.jsonl` — core_project_num ↔ pmid associations
- `publications.jsonl` — Europe PMC publication metadata
- `icite.jsonl` — iCite citation metrics

## CLI Usage

```bash
uv run python main.py --config collection.yaml --output-dir output
uv run python main.py -v  # verbose/debug logging
```
