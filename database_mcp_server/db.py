"""Read-only DuckDB query execution for the MCP server."""

import logging
import re
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# Only allow read-only statement types
_ALLOWED_PREFIXES = re.compile(
    r"^\s*(SELECT|WITH|SHOW|DESCRIBE|PRAGMA|EXPLAIN|SUMMARIZE)\b",
    re.IGNORECASE,
)

DEFAULT_DB_PATH = Path("output/icc-eval.duckdb")


class ReadOnlyDatabase:
    """Read-only DuckDB connection with query validation."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        if not db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {db_path}. "
                "Run 'python -m database_mcp_server.materialize' first."
            )
        self._db_path = db_path
        self._con = duckdb.connect(str(db_path), read_only=True)
        # Disable external file access (blocks read_csv, read_json, glob, httpfs, etc.)
        self._con.execute("SET enable_external_access = false")

    def execute_query(self, sql: str, limit: int = 100) -> list[dict]:
        """Execute a read-only SQL query and return results as a list of dicts.

        Args:
            sql: SQL query (must be SELECT, WITH, SHOW, DESCRIBE, PRAGMA, or EXPLAIN).
            limit: Maximum number of rows to return (default 100, max 10000).

        Returns:
            List of dicts, one per row, with column names as keys.

        Raises:
            ValueError: If the query is not a read-only statement.
        """
        if not _ALLOWED_PREFIXES.match(sql):
            raise ValueError(
                "Only read-only queries are allowed (SELECT, WITH, SHOW, DESCRIBE, PRAGMA, EXPLAIN, SUMMARIZE)."
            )

        limit = max(1, min(limit, 10000))

        # Wrap in a LIMIT if not already present to avoid runaway queries
        wrapped = f"SELECT * FROM ({sql}) AS _q LIMIT {limit}"

        logger.debug("Executing query (limit=%d): %s", limit, sql[:200])
        result = self._con.execute(wrapped)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def get_table_names(self) -> list[str]:
        """Return list of table names in the database."""
        result = self._con.execute("SHOW TABLES")
        return [row[0] for row in result.fetchall()]

    def close(self) -> None:
        self._con.close()
