from collections.abc import Generator

import duckdb
import pytest

from sqlmat.test import SchemaRegistry, Table


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
def src_schema(registry: SchemaRegistry) -> str:
    return registry.create_schema(prefix="staging")


@pytest.fixture
def tgt_schema(registry: SchemaRegistry) -> str:
    return registry.create_schema(prefix="analytics")


@pytest.fixture
def src_table(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, src_schema: str) -> Table:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return Table(conn, src_schema, "events", columns).create(registry)


@pytest.fixture
def tgt_table(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str) -> Table:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return Table(conn, tgt_schema, "daily_stats", columns).create(registry)
