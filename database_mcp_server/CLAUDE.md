# database_mcp_server — CLAUDE.md


Local guidance for the MCP server package. See the root `CLAUDE.md` for the overall project.

## Quick Reference

- **Materialize**: `uv run python -m database_mcp_server.materialize`
- **Run server**: `uv run python -m database_mcp_server.server`
- **Dependencies**: `mcp[cli]`, `duckdb` (in root pyproject.toml)

## Module Layout

```
database_mcp_server/
├── __init__.py          # empty
├── __main__.py          # entry: python -m database_mcp_server
├── materialize.py       # JSONL → DuckDB materialization
├── db.py                # ReadOnlyDatabase: validated SQL execution
└── server.py            # FastMCP server with query_sql, list_tables, describe_table
```

## Key Design Decisions

- **Separate from ETL** — this package has no imports from `icc_eval_etl`; it only consumes the `.duckdb` file
- **Read-only by design** — three security layers: regex prefix guard, `read_only=True` connection, `enable_external_access = false`
- **Single `query_sql` tool** — the tool description embeds full schema + examples so LLMs can compose SQL without separate schema resources
- **`describe_table` injection guard** — validates table name against `get_table_names()` before interpolation

## Materialization

`materialize.py` reads `icc-data-views.sql` (from the repo root), creates views over the JSONL files, then materializes each view as a permanent table. The view names in `VIEW_NAMES` must match those in the SQL file.

If new views are added to `icc-data-views.sql`, update `VIEW_NAMES` in `materialize.py`.

## Server Configuration

FastMCP host/port are set via `mcp.settings.host` and `mcp.settings.port` — they cannot be passed to `mcp.run()` directly.

Transport is `streamable-http`. The MCP endpoint is at `/mcp` (FastMCP default `streamable_http_path`).

## Gotchas

- DuckDB `read_only=True` does NOT block `COPY TO` or file-reading functions — that's why `enable_external_access = false` is essential
- The `_db` global in `server.py` is initialized in `main()` before `mcp.run()` — tools access it via `_get_db()`
- Row limit max is 10,000 (hardcoded in `db.py`)
