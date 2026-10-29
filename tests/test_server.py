"""MCP server tests: tools via an in-process MCP client, plus OTel span attributes."""

import json

import anyio
import duckdb
import pytest
from mcp.client import Client
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from database_mcp_server import server
from database_mcp_server.db import ReadOnlyDatabase

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE projects AS SELECT * FROM (VALUES (1, 'a'), (2, 'b')) t(appl_id, title)")
    con.close()
    monkeypatch.setattr(server, "_db", ReadOnlyDatabase(path))
    _exporter.clear()


def call(name, **args):
    async def go():
        async with Client(server.mcp) as c:
            r = await c.call_tool(name, args)
            return json.loads(r.content[0].text)

    return anyio.run(go)


def test_query_sql_ok_and_traced():
    assert call("query_sql", sql="SELECT * FROM projects ORDER BY appl_id") == [
        {"appl_id": 1, "title": "a"},
        {"appl_id": 2, "title": "b"},
    ]
    span = next(s for s in _exporter.get_finished_spans() if s.name == "tools/call query_sql")
    assert span.attributes["gen_ai.tool.name"] == "query_sql"
    assert span.attributes["db.query.text"] == "SELECT * FROM projects ORDER BY appl_id"
    assert span.attributes["db.response.returned_rows"] == 2


def test_bad_sql_returns_error_json():
    # v2 hides unhandled exception text, but our tools catch errors and return them as JSON.
    assert "nope does not exist" in call("query_sql", sql="SELECT * FROM nope")["error"]
    span = next(s for s in _exporter.get_finished_spans() if s.name == "tools/call query_sql")
    assert span.attributes["db.query.text"] == "SELECT * FROM nope"
    assert not span.status.is_ok


@pytest.mark.parametrize("sql", ["DROP TABLE projects", "COPY projects TO 'x.csv'"])
def test_write_sql_blocked(sql):
    assert "read-only" in call("query_sql", sql=sql)["error"]


def test_external_access_blocked():
    assert "Query failed" in call("query_sql", sql="SELECT * FROM read_csv('/etc/passwd')")["error"]


def test_list_and_describe():
    assert call("list_tables") == ["projects"]
    assert [c["column_name"] for c in call("describe_table", table_name="projects")] == ["appl_id", "title"]
    assert "Unknown table" in call("describe_table", table_name="x; DROP")["error"]
