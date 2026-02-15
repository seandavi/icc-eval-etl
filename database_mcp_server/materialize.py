"""Materialize JSONL views into a DuckDB database file.

Reads icc-data-views.sql to create views over the JSONL output files,
then materializes each view as a permanent table in output/icc-eval.duckdb.

Usage:
    uv run python -m database_mcp_server.materialize
    uv run python -m database_mcp_server.materialize --output output/icc-eval.duckdb
"""

import argparse
import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

VIEWS_SQL = Path(__file__).resolve().parent.parent / "icc-data-views.sql"

# View names to materialize, in order.
# Must match the view names defined in icc-data-views.sql.
VIEW_NAMES = [
    "projects",
    "publication_links",
    "publications",
    "icite",
    "citation_links",
    "citing_icite",
    "openalex",
    "citing_openalex",
    "github_repos",
]


def materialize(output_path: Path, views_sql: Path = VIEWS_SQL) -> None:
    """Create a DuckDB file with materialized tables from JSONL views."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing file to start fresh
    if output_path.exists():
        output_path.unlink()

    con = duckdb.connect(str(output_path))
    try:
        # Execute the views SQL to create views over JSONL files
        logger.info("Loading views from %s", views_sql)
        con.execute(views_sql.read_text())

        # Materialize each view as a table
        for view in VIEW_NAMES:
            logger.info("Materializing %s...", view)
            con.execute(f"CREATE TABLE {view}_tbl AS SELECT * FROM {view}")
            count = con.execute(f"SELECT count(*) FROM {view}_tbl").fetchone()[0]
            logger.info("  %s: %d rows", view, count)

            # Drop the view and rename the table to take its place
            con.execute(f"DROP VIEW {view}")
            con.execute(f"ALTER TABLE {view}_tbl RENAME TO {view}")

        logger.info("Materialized %d tables into %s", len(VIEW_NAMES), output_path)
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize JSONL views into DuckDB")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/icc-eval.duckdb"),
        help="Output DuckDB file path (default: output/icc-eval.duckdb)",
    )
    parser.add_argument(
        "--views-sql",
        type=Path,
        default=VIEWS_SQL,
        help="Path to icc-data-views.sql",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    materialize(args.output, args.views_sql)


if __name__ == "__main__":
    main()
