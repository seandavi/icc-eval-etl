# Deployment

The MCP server runs as a Docker container on on-prem hardware, fronted by Traefik for TLS termination and routing.

## Architecture

```
Internet
  │
  ▼
Cloudflare DNS (icc-eval-mcp.cancerdatasci.org)
  │
  ▼
Traefik (docker, shared `proxy` network)
  │  TLS termination (Let's Encrypt via TLS-ALPN challenge)
  │  Routes by Host header
  ▼
icc-eval-etl-mcp-server (docker, port 8000)
  │  Streamable HTTP transport
  ▼
DuckDB (read-only, baked into image)
```

## Prerequisites

- Docker and Docker Compose
- External docker network `proxy` (`docker network create proxy`)
- Traefik running on the `proxy` network with the `cloudflare` certresolver configured
- Cloudflare DNS A record for `icc-eval-mcp.cancerdatasci.org` pointing to the host
- Materialized DuckDB file at `output/icc-eval.duckdb`

## Building and deploying

The DuckDB file must exist before building the image since it gets baked in:

```bash
# Materialize JSONL data into DuckDB (if not already done)
uv run python -m database_mcp_server.materialize

# Build and start
docker compose up -d --build

# Check logs
docker compose logs -f

# Stop
docker compose down
```

## Updating the data

The database is baked into the Docker image at build time. To update:

1. Re-run the ETL pipeline: `uv run python main.py`
2. Re-materialize: `uv run python -m database_mcp_server.materialize`
3. Rebuild and redeploy: `docker compose up -d --build`

## MCP endpoint

```
https://icc-eval-mcp.cancerdatasci.org/mcp
```

Transport: `streamable-http`

## Key configuration notes

- **DNS rebinding protection** is disabled in the MCP server (`server.py`) because Traefik handles host validation and TLS upstream. `MCPServer.run()` enables it by default when bound to localhost, which conflicts with reverse-proxy deployments.
- **Read-only filesystem** — the container runs with `read_only: true` and a tmpfs at `/tmp`. The CMD invokes the venv Python directly (`/app/.venv/bin/python`) rather than `uv run`, which would try to write to the venv at runtime.
- **Non-root user** — the container runs as `appuser`.

## Tracing (OpenTelemetry)

mcp 2.x wraps every MCP request in an OpenTelemetry span (`tools/call query_sql`, with `gen_ai.tool.name`, `jsonrpc.request.id`, ...). `query_sql` adds `db.query.text` (first 200 chars), `db.response.returned_rows` and an error status for failed queries. Clients that send a W3C `traceparent` in `_meta` get their traces joined to ours.

Tracing is off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set; with it unset the server behaves exactly as before. Standard env vars, passed through by `docker-compose.yaml`:

| Variable | Example | Notes |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` | Enables tracing |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | Default `grpc` (port 4317) |
| `OTEL_EXPORTER_OTLP_HEADERS` | `authorization=Bearer%20xyz` | Auth for hosted backends |
| `OTEL_SERVICE_NAME` | `icc-eval-mcp` | Defaults to `icc-eval-mcp` |

Only traces are exported (`OTEL_METRICS_EXPORTER` / `OTEL_LOGS_EXPORTER` default to `none`). While a span is active, loguru JSON records carry `trace_id` and `span_id` in `extra`.

Quick local check with a collector printing spans:

```bash
docker run --rm -p 4318:4318 otel/opentelemetry-collector  # use a config with an otlp receiver and `debug` exporter (verbosity: detailed) to see span attributes
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
  uv run python -m database_mcp_server.server
```
