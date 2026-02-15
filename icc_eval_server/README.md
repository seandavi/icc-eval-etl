# icc_eval_server

MCP server that exposes the ICC grant evaluation data via read-only SQL queries over DuckDB.

## Usage

A public instance is available at `https://icc-eval-mcp.cancerdatasci.org/mcp` (streamable HTTP transport). No authentication required.

### Claude Desktop / Claude Code

Add to your MCP server configuration (`~/.claude/settings.json` for Claude Code, or Claude Desktop settings):

```json
{
  "mcpServers": {
    "icc-eval": {
      "url": "https://icc-eval-mcp.cancerdatasci.org/mcp"
    }
  }
}
```

# Local development

This section covers local development. For deployment notes, see [DEPLOYMENT.md](DEPLOYMENT.md)

## Quick start

```bash
# 1. Run the ETL pipeline (if not already done)
uv run python main.py

# 2. Materialize JSONL into a DuckDB database
uv run python -m icc_eval_server.materialize

# 3. Start the MCP server
uv run python -m icc_eval_server.server
```

The server starts on `http://0.0.0.0:8000` with the MCP endpoint at `/mcp`.

## Commands

### Materialize

Converts the JSONL output files into a single DuckDB database file.

```bash
uv run python -m icc_eval_server.materialize [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--output` | `output/icc-eval.duckdb` | Output database path |
| `--views-sql` | `icc-data-views.sql` | Path to view definitions |
| `-v` | off | Debug logging |

### Server

Runs the FastMCP server with streamable HTTP transport.

```bash
uv run python -m icc_eval_server.server [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--db` | `output/icc-eval.duckdb` | Path to DuckDB database |
| `--host` | `0.0.0.0` | Host to bind to |
| `--port` | `8000` | Port to listen on |
| `-v` | off | Debug logging |

## MCP Tools

### `query_sql(sql, limit=100)`

Execute a read-only SQL query. The tool description includes full table schemas and example queries so LLM clients can compose SQL without needing separate schema discovery.

### `list_tables()`

Returns the list of available table names.

### `describe_table(table_name)`

Returns column names, types, and nullability for a given table.

## Tables

| Table | Rows | Description |
|-------|------|-------------|
| `projects` | 80 | NIH Reporter grant records (one row per project-year) |
| `publication_links` | 154 | Core project num to PMID join table |
| `publications` | 141 | Europe PMC publication metadata |
| `icite` | 141 | iCite citation metrics for grant-associated publications |
| `citation_links` | 1,298 | Cited PMID to citing PMID edge list |
| `citing_icite` | 1,234 | iCite metrics for citing publications |
| `openalex` | 140 | OpenAlex work records for grant-associated publications |
| `citing_openalex` | 1,228 | OpenAlex work records for citing publications |
| `github_repos` | 29 | GitHub repos tagged with project ID topics |

## Security

Three layers of read-only enforcement:

1. **SQL prefix validation** — only `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `PRAGMA`, `EXPLAIN`, `SUMMARIZE` allowed
2. **DuckDB `read_only=True`** — connection-level write protection
3. **`enable_external_access = false`** — blocks `read_csv`, `glob`, `httpfs`, and other file-system functions

The `describe_table` tool validates table names against the actual table list to prevent SQL injection.

## Docker

```bash
# Build (requires output/icc-eval.duckdb to exist)
docker build -t icc-eval-server .

# Run
docker run -p 8000:8000 icc-eval-server
```



### Python client

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

async with streamablehttp_client("https://icc-eval-mcp.cancerdatasci.org/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("query_sql", {
            "sql": "SELECT count(*) FROM projects"
        })
```

### Local development

If running the server locally, replace the URL with `http://localhost:8000/mcp`.
