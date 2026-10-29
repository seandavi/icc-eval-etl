# database_mcp_server — CLAUDE.md


Local guidance for the MCP server package. See the root `CLAUDE.md` for the overall project.

## Quick Reference

- **Materialize**: `uv run python -m database_mcp_server.materialize`
- **Run server**: `uv run python -m database_mcp_server.server`
- **Dependencies**: `mcp[cli]>=2.3,<3`, `duckdb`, `opentelemetry-distro`, `opentelemetry-exporter-otlp` (in root pyproject.toml)
- **Tests**: `uv run pytest tests`

## Module Layout

```
database_mcp_server/
├── __init__.py          # empty
├── __main__.py          # entry: python -m database_mcp_server
├── materialize.py       # JSONL → DuckDB materialization
├── db.py                # ReadOnlyDatabase: validated SQL execution
└── server.py            # MCPServer (mcp 2.x) with query_sql, list_tables, describe_table
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

The server is `mcp.server.mcpserver.MCPServer` (mcp 2.x, replaces `FastMCP`). Host, port and transport security are passed to `mcp.run(transport="streamable-http", host=..., port=..., transport_security=...)` — setting `mcp.settings.host/port` raises `ValueError` in v2.

Transport is `streamable-http`. The MCP endpoint is at `/mcp` (default `streamable_http_path`).

## Tracing

The SDK's OTel middleware creates a span per MCP request. `_configure_tracing()` in `main()` installs a tracer provider via `opentelemetry.instrumentation.auto_instrumentation.initialize()` only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; otherwise spans are no-ops. Tools enrich the current span with `trace.get_current_span()` (sync tools run in a worker thread, contextvars carry the span). Env vars: see `DEPLOYMENT.md`.

## Gotchas

- DuckDB `read_only=True` does NOT block `COPY TO` or file-reading functions — that's why `enable_external_access = false` is essential
- The `_db` global in `server.py` is initialized in `main()` before `mcp.run()` — tools access it via `_get_db()`
- `ctx.client_id` no longer exists in v2; `ctx.request_id` may be `None`
- v2 hides unhandled exception text from clients — tools must keep catching errors and returning `{"error": ...}` JSON
- Row limit max is 10,000 (hardcoded in `db.py`)
