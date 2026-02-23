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
    with SchemaRegistry(conn) as r:
        yield r


def test_insert_tuples(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)

    table.insert([(1, "Alice"), (2, "Bob")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        order_by=["id"],
    )


def test_insert_dicts(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar"), ("age", "integer")]).create(registry)

    table.insert([{"id": 1, "name": "Alice", "age": 30}, {"id": 2, "name": "Bob", "age": 25}])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice", "age": 30}, {"id": 2, "name": "Bob", "age": 25}],
        order_by=["id"],
    )


def test_insert_dicts_with_defaults(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    columns = [("user_id", "integer"), ("event_date", "varchar"), ("event_count", "integer")]
    table = DuckDBTable(conn, "main", "events", columns).create(registry)

    table.insert(
        [{"user_id": 1, "event_count": 5}, {"user_id": 2, "event_count": 3}],
        defaults={"event_date": "2024-01-01"},
    )

    table.assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-01", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_insert_dicts_row_overrides_defaults(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    columns = [("user_id", "integer"), ("event_date", "varchar"), ("event_count", "integer")]
    table = DuckDBTable(conn, "main", "events", columns).create(registry)

    table.insert(
        [{"user_id": 1, "event_date": "2024-06-15", "event_count": 5}],
        defaults={"event_date": "2024-01-01"},
    )

    table.assert_table_equals(
        [{"user_id": 1, "event_date": "2024-06-15", "event_count": 5}],
    )


def test_delete_all(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    table.delete()

    table.assert_table_equals([])


def test_delete_with_where(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob"), (3, "Charlie")])

    table.delete("id = 2")

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}],
        order_by=["id"],
    )


def test_create_schema_with_prefix(conn: duckdb.DuckDBPyConnection) -> None:
    with SchemaRegistry(conn) as registry:
        schema = registry.create_schema(prefix="staging")

        assert schema.startswith("staging_")
        table = DuckDBTable(conn, schema, "events", [("id", "integer")]).create(registry)
        table.assert_table_equals([])

    assert conn.cursor().execute(f"select schema_name from information_schema.schemata where schema_name = '{schema}'").fetchall() == []


def test_create_schema_without_prefix(conn: duckdb.DuckDBPyConnection) -> None:
    with SchemaRegistry(conn) as registry:
        schema = registry.create_schema()

        table = DuckDBTable(conn, schema, "events", [("id", "integer")]).create(registry)
        table.assert_table_equals([])

    assert conn.cursor().execute(f"select schema_name from information_schema.schemata where schema_name = '{schema}'").fetchall() == []


def test_assert_table_equals_without_order_by(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(2, "Bob"), (1, "Alice")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
    )


def test_assert_table_equals_subset_of_columns(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar"), ("age", "integer")]).create(registry)
    table.insert([(1, "Alice", 30), (2, "Bob", 25)])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        columns=["id", "name"],
        order_by=["id"],
    )


def test_assert_table_equals_fails_on_mismatch(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    with pytest.raises(AssertionError):
        table.assert_table_equals([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Charlie"}])


def test_assert_table_contains_subset(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob"), (3, "Charlie")])

    table.assert_table_contains([{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}])


def test_assert_table_contains_fails_when_row_missing(conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry) -> None:
    table = DuckDBTable(conn, "main", "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    with pytest.raises(AssertionError, match="Expected row not found"):
        table.assert_table_contains([{"id": 3, "name": "Charlie"}])
