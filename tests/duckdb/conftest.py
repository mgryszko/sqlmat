from collections.abc import Generator

import duckdb
import pytest

from sqlmat.test import DuckDBTable, SchemaRegistry


@pytest.fixture
def conn() -> Generator[duckdb.DuckDBPyConnection]:
    with duckdb.connect(":memory:") as c:
        yield c


@pytest.fixture
def registry(conn: duckdb.DuckDBPyConnection) -> Generator[SchemaRegistry]:
    r = SchemaRegistry(conn)
    yield r
    r.teardown()


@pytest.fixture
def schema(registry: SchemaRegistry) -> str:
    return registry.create_schema(prefix="test")


@pytest.fixture
def src_table(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, schema: str) -> DuckDBTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return DuckDBTable(conn, schema, "events", columns).create(registry)


@pytest.fixture
def tgt_table(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, schema: str) -> DuckDBTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return DuckDBTable(conn, schema, "daily_stats", columns).create(registry)
