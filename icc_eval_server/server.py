"""MCP server exposing ICC evaluation data via read-only SQL queries.

Usage:
    uv run python -m icc_eval_server.server
    uv run python -m icc_eval_server.server --db output/icc-eval.duckdb --port 8000
"""

import argparse
import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from icc_eval_server.db import ReadOnlyDatabase

logger = logging.getLogger(__name__)

TOOL_DESCRIPTION = """\
Execute a read-only SQL query against the ICC grant evaluation database.

This database contains NIH grant records, associated publications, citation
metrics, OpenAlex work records, and GitHub repositories for a collection of
NIH-funded projects.

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

mcp = FastMCP(
    "ICC Grant Evaluation Data",
    instructions=(
        "This server provides read-only SQL access to NIH grant evaluation data "
        "including grants, publications, citation metrics, OpenAlex records, and "
        "GitHub repositories. Use the query_sql tool to run SQL queries."
    ),
)

# Will be initialized on startup
_db: ReadOnlyDatabase | None = None


def _get_db() -> ReadOnlyDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


@mcp.tool(description=TOOL_DESCRIPTION)
def query_sql(sql: str, limit: int = 100) -> str:
    """Execute a read-only SQL query against the ICC evaluation database."""
    db = _get_db()
    try:
        results = db.execute_query(sql, limit=limit)
        return json.dumps(results, default=str)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.exception("Query failed: %s", sql[:200])
        return json.dumps({"error": f"Query failed: {e}"})


@mcp.tool()
def list_tables() -> str:
    """List all available tables in the ICC evaluation database."""
    db = _get_db()
    tables = db.get_table_names()
    return json.dumps(tables)


@mcp.tool()
def describe_table(table_name: str) -> str:
    """Describe the columns and types of a table.

    Example: describe_table("projects") returns column names, types, and nullability.
    """
    db = _get_db()
    if table_name not in db.get_table_names():
        return json.dumps({"error": f"Unknown table: {table_name}. Use list_tables() to see available tables."})
    try:
        results = db.execute_query(f"DESCRIBE {table_name}", limit=1000)
        return json.dumps(results, default=str)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe table: {e}"})


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

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _db = ReadOnlyDatabase(args.db)
    logger.info("Loaded database: %s", args.db)
    logger.info("Tables: %s", _db.get_table_names())

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
