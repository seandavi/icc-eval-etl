"""MCP server exposing ICC evaluation data via read-only SQL queries.

Usage:
    uv run python -m database_mcp_server.server
    uv run python -m database_mcp_server.server --db output/icc-eval.duckdb --port 8000
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from loguru import logger
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from database_mcp_server.db import ReadOnlyDatabase

TOOL_DESCRIPTION = """\
Execute a read-only SQL query against the CFDE grant evaluation database.

This database covers a fixed set of about a dozen NIH Common Fund Data
Ecosystem (CFDE) grants (OT2/U54/U24, FY2019 onward): NIH RePORTER funding
records, linked publications, citation metrics, OpenAlex work records, the
papers that cite them, and GitHub repositories tagged with the grant IDs.
It does not cover NIH as a whole.

## Notes

- `projects` has one row per project-year. Group by core_project_num to count
  or describe grants; SUM(award_amount) over all rows gives total funding.
- core_project_num values are uppercase, e.g. 'OT2OD030161'.
- `icite`/`openalex` describe the grants' own publications; `citing_icite`/
  `citing_openalex` describe the papers that cite them (via citation_links).
- Some grants have no linked publications; that is real data, not an error.
- List the grants with:
  SELECT DISTINCT core_project_num, project_title FROM projects

## Tables

### projects
NIH Reporter grant records, one row per project-year.
Columns: appl_id, project_num, core_project_num, project_title, fiscal_year,
award_amount, direct_cost_amt, indirect_cost_amt, activity_code, funding_mechanism,
agency_code, is_active, is_new, contact_pi_name, org_name, org_city, org_state,
org_country, project_start_date, project_end_date, budget_start, budget_end,
award_notice_date, pref_terms, abstract_text

### publication_links
Join table: core_project_num <-> pmid (which publications are linked to which grants).
Columns: core_project_num, pmid, appl_id

### publications
Europe PMC publication metadata, one row per PMID.
Columns: pmid, doi, pmcid, title, author_string, pub_year, journal_title,
journal_abbrev, cited_by_count, is_open_access, language, pub_model, source,
abstract_text, first_publication_date

### icite
iCite citation metrics for grant-associated publications.
Columns: pmid, title, doi, year, journal, citation_count, citations_per_year,
rcr (relative citation ratio), expected_citations_per_year, field_citation_rate,
nih_percentile, is_research_article, is_clinical, provisional, cited_by,
references, cited_by_count, reference_count

### citation_links
Edge list: cited_pmid <-> citing_pmid (which papers cite the grant publications).
Columns: cited_pmid, citing_pmid

### citing_icite
iCite metrics for citing publications (same schema as icite).

### openalex
OpenAlex work records for grant-associated publications.
Columns: openalex_id, doi, title, display_name, publication_year, publication_date,
pmid_url, pmid, type, language, primary_source, is_oa, oa_status, cited_by_count,
fwci, volume, issue, first_page, last_page, is_retracted, referenced_works_count,
primary_topic, primary_subfield, author_count, topic_count, mesh_count

### citing_openalex
OpenAlex work records for citing publications (same schema as openalex).

### github_repos
GitHub repositories tagged with project ID topics.
Columns: repo_id, name, full_name, html_url, description, topics, core_project_ids,
language, stars, forks, open_issues, owner_login, owner_type, license_name,
created_at, updated_at, pushed_at, is_private, is_fork, is_archived

## Example queries

-- List all grants with total award amounts
SELECT core_project_num, project_title, SUM(award_amount) as total_funding
FROM projects GROUP BY core_project_num, project_title

-- Top 10 most-cited grant publications
SELECT p.pmid, p.title, i.citation_count, i.rcr, i.nih_percentile
FROM publications p JOIN icite i ON p.pmid = i.pmid
ORDER BY i.citation_count DESC LIMIT 10

-- Publications per grant
SELECT pl.core_project_num, COUNT(DISTINCT pl.pmid) as pub_count
FROM publication_links pl GROUP BY pl.core_project_num ORDER BY pub_count DESC

-- Open access status of grant publications
SELECT o.oa_status, COUNT(*) as count
FROM openalex o GROUP BY o.oa_status ORDER BY count DESC

-- GitHub repos with most stars
SELECT name, html_url, stars, language, description
FROM github_repos ORDER BY stars DESC LIMIT 10

-- Citation network: who cites our grant publications the most?
SELECT ci.journal, COUNT(*) as citation_count, AVG(ci.rcr) as avg_rcr
FROM citation_links cl JOIN citing_icite ci ON cl.citing_pmid = ci.pmid
GROUP BY ci.journal ORDER BY citation_count DESC LIMIT 10
"""

mcp = MCPServer(
    "ICC Grant Evaluation Data",
    instructions=(
        "Read-only SQL access to evaluation data for the NIH Common Fund Data "
        "Ecosystem (CFDE): a fixed set of about a dozen CFDE-funded grants "
        "(OT2/U54/U24, FY2019 onward). For each grant: NIH RePORTER funding "
        "records, linked publications (Europe PMC), citation metrics (iCite "
        "RCR/NIH percentile, OpenAlex FWCI/open access), the papers that cite "
        "them, and GitHub repositories tagged with the grant ID. Use it to answer "
        "questions about this portfolio's funding, publications, scholarly "
        "impact, and software; it does not cover NIH as a whole. Query with "
        "query_sql; run SELECT DISTINCT core_project_num, project_title FROM "
        "projects to see the grant list."
    ),
)

# Will be initialized on startup
_db: ReadOnlyDatabase | None = None


def _get_db() -> ReadOnlyDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


@mcp.tool(description=TOOL_DESCRIPTION)
def query_sql(sql: str, limit: int = 100, ctx: Context | None = None) -> str:
    """Execute a read-only SQL query against the ICC evaluation database."""
    db = _get_db()
    t0 = time.perf_counter()
    request_id = ctx.request_id if ctx else None
    # Enrich the SDK's "tools/call query_sql" span; a no-op without a tracer provider.
    span = trace.get_current_span()
    span.set_attributes({"db.system.name": "duckdb", "db.query.text": sql[:200]})
    try:
        results = db.execute_query(sql, limit=limit)
        duration_ms = (time.perf_counter() - t0) * 1000
        span.set_attribute("db.response.returned_rows", len(results))
        logger.bind(
            tool="query_sql",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="ok",
            sql=sql[:200],
            limit=limit,
            row_count=len(results),
        ).info("tool_call")
        return json.dumps(results, default=str)
    except ValueError as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="query_sql",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="error",
            error=str(e),
            sql=sql[:200],
            limit=limit,
        ).warning("tool_call")
        span.set_status(StatusCode.ERROR, str(e))
        return json.dumps({"error": str(e)})
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="query_sql",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="error",
            error=str(e),
            sql=sql[:200],
            limit=limit,
        ).error("tool_call")
        span.set_status(StatusCode.ERROR, str(e))
        return json.dumps({"error": f"Query failed: {e}"})


@mcp.tool()
def list_tables(ctx: Context | None = None) -> str:
    """List all available tables in the ICC evaluation database."""
    db = _get_db()
    t0 = time.perf_counter()
    request_id = ctx.request_id if ctx else None
    try:
        tables = db.get_table_names()
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="list_tables",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="ok",
            table_count=len(tables),
        ).info("tool_call")
        return json.dumps(tables)
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="list_tables",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="error",
            error=str(e),
        ).error("tool_call")
        return json.dumps({"error": f"Failed to list tables: {e}"})


@mcp.tool()
def describe_table(table_name: str, ctx: Context | None = None) -> str:
    """Describe the columns and types of a table.

    Example: describe_table("projects") returns column names, types, and nullability.
    """
    db = _get_db()
    t0 = time.perf_counter()
    request_id = ctx.request_id if ctx else None
    if table_name not in db.get_table_names():
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="describe_table",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="error",
            error=f"Unknown table: {table_name}",
            table_name=table_name,
        ).warning("tool_call")
        return json.dumps({"error": f"Unknown table: {table_name}. Use list_tables() to see available tables."})
    try:
        results = db.execute_query(f"DESCRIBE {table_name}", limit=1000)
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="describe_table",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="ok",
            table_name=table_name,
            column_count=len(results),
        ).info("tool_call")
        return json.dumps(results, default=str)
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        logger.bind(
            tool="describe_table",
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            status="error",
            error=str(e),
            table_name=table_name,
        ).error("tool_call")
        return json.dumps({"error": f"Failed to describe table: {e}"})


def _configure_tracing() -> None:
    """Export the SDK's spans over OTLP, configured by the standard OTEL_* env vars.

    Without OTEL_EXPORTER_OTLP_ENDPOINT no tracer provider is installed, so spans stay no-ops.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    os.environ.setdefault("OTEL_SERVICE_NAME", "icc-eval-mcp")
    # Only traces are wanted; the distro would otherwise also push metrics and logs.
    os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
    os.environ.setdefault("OTEL_LOGS_EXPORTER", "none")
    from opentelemetry.instrumentation.auto_instrumentation import initialize

    initialize()
    logger.info("OpenTelemetry tracing enabled: {endpoint}", endpoint=endpoint)


def _add_trace_ids(record) -> None:
    """Stamp the active OTel trace/span ids on log records so logs and traces line up."""
    span_ctx = trace.get_current_span().get_span_context()
    if span_ctx.is_valid:
        record["extra"]["trace_id"] = format(span_ctx.trace_id, "032x")
        record["extra"]["span_id"] = format(span_ctx.span_id, "016x")


class _InterceptHandler(logging.Handler):
    """Route stdlib logging into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def main() -> None:
    global _db

    parser = argparse.ArgumentParser(description="ICC Evaluation MCP Server")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("output/icc-eval.duckdb"),
        help="Path to DuckDB database file",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    # Configure loguru: JSON-serialized logs to stderr
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if args.verbose else "INFO",
        serialize=True,
    )
    logger.configure(patcher=_add_trace_ids)

    # Intercept stdlib logging (uvicorn, mcp library) into loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    _configure_tracing()

    _db = ReadOnlyDatabase(args.db)
    logger.info("Loaded database: {db_path}", db_path=str(args.db))
    logger.info("Tables: {tables}", tables=_db.get_table_names())

    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


if __name__ == "__main__":
    main()
