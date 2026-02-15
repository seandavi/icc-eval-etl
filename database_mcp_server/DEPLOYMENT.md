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

- **DNS rebinding protection** is disabled in the MCP server (`server.py`) because Traefik handles host validation and TLS upstream. The `FastMCP` default constructor enables it for localhost, which conflicts with reverse-proxy deployments.
- **Read-only filesystem** — the container runs with `read_only: true` and a tmpfs at `/tmp`. The CMD invokes the venv Python directly (`/app/.venv/bin/python`) rather than `uv run`, which would try to write to the venv at runtime.
- **Non-root user** — the container runs as `appuser`.
