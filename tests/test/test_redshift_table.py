from collections.abc import Generator

import pytest
import redshift_connector
from env import RedshiftEnv

from sqlmat.test import RedshiftTable, RedshiftTx, SchemaRegistry


@pytest.fixture(scope="module")
def conn(redshift_env: RedshiftEnv) -> Generator[redshift_connector.Connection]:
    c = redshift_connector.connect(
        host=redshift_env.host,
        port=redshift_env.port,
        database=redshift_env.database,
        user=redshift_env.user,
        password=redshift_env.password,
    )
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture
def registry(conn: redshift_connector.Connection) -> Generator[SchemaRegistry]:
    with SchemaRegistry(conn) as r:
        yield r


@pytest.fixture
def schema(registry: SchemaRegistry, redshift_env: RedshiftEnv) -> str:
    return registry.create_schema(prefix=redshift_env.schema_prefix)


def test_insert_tuples(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)

    table.insert([(1, "Alice"), (2, "Bob")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        order_by=["id"],
    )


def test_insert_tuples_with_wrapped_column(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "events", [("id", "integer"), ("payload", "super", "json_parse({})")]).create(registry)

    table.insert([(1, '{"key": "value"}'), (2, '{"key": "other"}')])

    table.assert_table_equals(
        [{"id": 1, "payload": '{"key":"value"}'}, {"id": 2, "payload": '{"key":"other"}'}],
        order_by=["id"],
    )


def test_insert_dicts_with_wrapped_column(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "events", [("id", "integer"), ("payload", "super", "json_parse({})")]).create(registry)

    table.insert([{"id": 1, "payload": '{"key": "value"}'}, {"id": 2, "payload": '{"key": "other"}'}])

    table.assert_table_equals(
        [{"id": 1, "payload": '{"key":"value"}'}, {"id": 2, "payload": '{"key":"other"}'}],
        order_by=["id"],
    )


def test_insert_dicts(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar"), ("age", "integer")]).create(registry)

    table.insert([{"id": 1, "name": "Alice", "age": 30}, {"id": 2, "name": "Bob", "age": 25}])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice", "age": 30}, {"id": 2, "name": "Bob", "age": 25}],
        order_by=["id"],
    )


def test_insert_dicts_with_defaults(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    columns = [("user_id", "integer"), ("event_date", "varchar"), ("event_count", "integer")]
    table = RedshiftTable(conn, schema, "events", columns).create(registry)

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


def test_insert_dicts_row_overrides_defaults(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    columns = [("user_id", "integer"), ("event_date", "varchar"), ("event_count", "integer")]
    table = RedshiftTable(conn, schema, "events", columns).create(registry)

    table.insert(
        [{"user_id": 1, "event_date": "2024-06-15", "event_count": 5}],
        defaults={"event_date": "2024-01-01"},
    )

    table.assert_table_equals(
        [{"user_id": 1, "event_date": "2024-06-15", "event_count": 5}],
    )


def test_delete_all(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    table.delete()

    table.assert_table_equals([])


def test_delete_with_where(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob"), (3, "Charlie")])

    table.delete("id = 2")

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}],
        order_by=["id"],
    )


def test_create_schema_with_prefix(conn: redshift_connector.Connection, redshift_env: RedshiftEnv) -> None:
    with SchemaRegistry(conn) as registry:
        schema = registry.create_schema(prefix=redshift_env.schema_prefix)

        assert schema.startswith(f"{redshift_env.schema_prefix}_")
        table = RedshiftTable(conn, schema, "events", [("id", "integer")]).create(registry)
        table.assert_table_equals([])

    cursor = conn.cursor()
    cursor.execute("select schema_name from information_schema.schemata where schema_name = %s", (schema,))
    assert cursor.fetchall() == ()


def test_create_schema_without_prefix(conn: redshift_connector.Connection) -> None:
    with SchemaRegistry(conn) as registry:
        schema = registry.create_schema()

        table = RedshiftTable(conn, schema, "events", [("id", "integer")]).create(registry)
        table.assert_table_equals([])

    cursor = conn.cursor()
    cursor.execute("select schema_name from information_schema.schemata where schema_name = %s", (schema,))
    assert cursor.fetchall() == ()


def test_assert_table_equals_without_order_by(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(2, "Bob"), (1, "Alice")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
    )


def test_assert_table_equals_subset_of_columns(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar"), ("age", "integer")]).create(registry)
    table.insert([(1, "Alice", 30), (2, "Bob", 25)])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        columns=["id", "name"],
        order_by=["id"],
    )


def test_assert_table_equals_fails_on_mismatch(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    with pytest.raises(AssertionError):
        table.assert_table_equals([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Charlie"}])


def test_assert_table_contains_subset(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob"), (3, "Charlie")])

    table.assert_table_contains([{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}])


def test_assert_table_contains_fails_when_row_missing(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    with pytest.raises(AssertionError, match="Expected row not found"):
        table.assert_table_contains([{"id": 3, "name": "Charlie"}])


def test_redshift_tx_commits_on_success(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)

    with RedshiftTx(conn):
        table.insert([(1, "Alice"), (2, "Bob")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        order_by=["id"],
    )


def test_redshift_tx_rolls_back_on_error(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> None:
    table = RedshiftTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")]).create(registry)
    table.insert([(1, "Alice")])

    def insert_and_fail() -> None:
        with RedshiftTx(conn):
            table.insert([(2, "Bob")])
            raise RuntimeError("simulated failure")

    with pytest.raises(RuntimeError):
        insert_and_fail()

    table.assert_table_equals([{"id": 1, "name": "Alice"}])
