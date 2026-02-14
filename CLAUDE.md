# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Detailed docs live in `agent_docs/` — see index below.

## Project Overview

ETL pipeline for gathering NIH grant evaluation data. Given NIH core project identifiers (in `collection.yaml`), fetches grant records, publications, citation metrics, OpenAlex works, and GitHub repos. All output is JSONL.

An MCP server (`icc_eval_server/`) exposes the data via read-only SQL queries over DuckDB.

## Quick Reference

- **Run ETL**: `uv run python main.py` (add `-v` for debug logging)
- **Materialize**: `uv run python -m icc_eval_server.materialize`
- **Run MCP server**: `uv run python -m icc_eval_server.server`
- **Install deps**: `uv sync`
- **Python**: 3.14 via `uv` (see `.python-version`)
- **Config**: `collection.yaml` — core project identifiers
- **Output**: `output/` (gitignored) — 9 JSONL files + `icc-eval.duckdb`
- **DuckDB**: `duckdb -init icc-data-views.sql`
- **Env vars**: `.env` loaded at startup (`GITHUB_TOKEN`, `OPENALEX_API_KEY`)

## Data Sources

1. **NIH Reporter** — grant projects + publication links
2. **Europe PMC** — publication metadata
3. **iCite** — citation metrics + cited_by graph
4. **OpenAlex** — rich work records (topics, FWCI, OA status)
5. **GitHub** — repos tagged with project ID topics

## Agent Docs Index

| Document | Contents |
|----------|----------|
| [`agent_docs/package-structure.md`](agent_docs/package-structure.md) | Full package tree, module descriptions, entry point |
| [`agent_docs/architecture.md`](agent_docs/architecture.md) | Client patterns, pipeline steps, output files |
| [`agent_docs/api-quirks.md`](agent_docs/api-quirks.md) | API-specific gotchas (NIH Reporter, Europe PMC, iCite, OpenAlex, GitHub) |
| [`icc_eval_server/CLAUDE.md`](icc_eval_server/CLAUDE.md) | MCP server design, security layers, gotchas |

## Key Conventions

- All HTTP clients are async (httpx) with shared `BaseClient` for rate limiting + retry
- Pydantic models use `extra="allow"` — capture full API responses without breaking on new fields
- GitHub client uses `tenacity` (separate retry logic) with exponential backoff
- MCP server is read-only with 3 security layers (see `icc_eval_server/CLAUDE.md`)
- `.env` loaded at startup via python-dotenv in `main.py`
