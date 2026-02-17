import uuid
from collections.abc import Generator

import pyathena
import pytest
from env import AthenaEnv

from sqlmat.test import AthenaTable, SchemaRegistry


@pytest.fixture(scope="module")
def conn(athena_env: AthenaEnv) -> Generator[pyathena.Connection]:
    c = pyathena.connect(
        s3_staging_dir=athena_env.s3_staging_dir,
        region_name=athena_env.region,
        work_group=athena_env.work_group,
    )
    yield c
    c.close()


@pytest.fixture
def s3_table_base_uri(athena_env: AthenaEnv) -> str:
    return f"{athena_env.s3_table_base_uri}/sqlmat_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def registry(conn: pyathena.Connection) -> Generator[SchemaRegistry]:
    r = SchemaRegistry(conn)
    yield r
    r.teardown()


@pytest.fixture
def schema(registry: SchemaRegistry, athena_env: AthenaEnv) -> str:
    return registry.create_schema(prefix=athena_env.schema_prefix)


def test_insert_tuples(conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)

    table.insert([(1, "Alice"), (2, "Bob")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        order_by=["id"],
    )


def test_insert_dicts(conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string"), ("age", "int")], s3_table_base_uri).create(registry)

    table.insert([{"id": 1, "name": "Alice", "age": 30}, {"id": 2, "name": "Bob", "age": 25}])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice", "age": 30}, {"id": 2, "name": "Bob", "age": 25}],
        order_by=["id"],
    )


def test_insert_dicts_with_defaults(conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> None:
    columns = [("user_id", "int"), ("event_date", "string"), ("event_count", "int")]
    table = AthenaTable(conn, schema, "events", columns, s3_table_base_uri).create(registry)

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


def test_insert_dicts_row_overrides_defaults(
    conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str
) -> None:
    columns = [("user_id", "int"), ("event_date", "string"), ("event_count", "int")]
    table = AthenaTable(conn, schema, "events", columns, s3_table_base_uri).create(registry)

    table.insert(
        [{"user_id": 1, "event_date": "2024-06-15", "event_count": 5}],
        defaults={"event_date": "2024-01-01"},
    )

    table.assert_table_equals(
        [{"user_id": 1, "event_date": "2024-06-15", "event_count": 5}],
    )


def test_delete_all(conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    table.delete()

    table.assert_table_equals([])


def test_delete_with_where(conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)
    table.insert([(1, "Alice"), (2, "Bob"), (3, "Charlie")])

    table.delete("id = 2")

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}],
        order_by=["id"],
    )


def test_create_schema_with_prefix(conn: pyathena.Connection, athena_env: AthenaEnv, s3_table_base_uri: str) -> None:
    registry = SchemaRegistry(conn)
    schema = registry.create_schema(prefix=athena_env.schema_prefix)

    assert schema.startswith(f"{athena_env.schema_prefix}_")
    table = AthenaTable(conn, schema, "events", [("id", "int")], s3_table_base_uri).create(registry)
    table.assert_table_equals([])

    registry.teardown()

    cursor = conn.cursor()
    cursor.execute("show databases")
    databases = [row[0] for row in cursor.fetchall()]
    assert schema not in databases


def test_create_schema_without_prefix(conn: pyathena.Connection, s3_table_base_uri: str) -> None:
    registry = SchemaRegistry(conn)
    schema = registry.create_schema()

    table = AthenaTable(conn, schema, "events", [("id", "int")], s3_table_base_uri).create(registry)
    table.assert_table_equals([])

    registry.teardown()

    cursor = conn.cursor()
    cursor.execute("show databases")
    databases = [row[0] for row in cursor.fetchall()]
    assert schema not in databases


def test_assert_table_equals_without_order_by(
    conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str
) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)
    table.insert([(2, "Bob"), (1, "Alice")])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
    )


def test_assert_table_equals_subset_of_columns(
    conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str
) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string"), ("age", "int")], s3_table_base_uri).create(registry)
    table.insert([(1, "Alice", 30), (2, "Bob", 25)])

    table.assert_table_equals(
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        columns=["id", "name"],
        order_by=["id"],
    )


def test_assert_table_equals_fails_on_mismatch(
    conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str
) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    with pytest.raises(AssertionError):
        table.assert_table_equals([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Charlie"}])


def test_assert_table_contains_subset(conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)
    table.insert([(1, "Alice"), (2, "Bob"), (3, "Charlie")])

    table.assert_table_contains([{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}])


def test_assert_table_contains_fails_when_row_missing(
    conn: pyathena.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str
) -> None:
    table = AthenaTable(conn, schema, "users", [("id", "int"), ("name", "string")], s3_table_base_uri).create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])

    with pytest.raises(AssertionError, match="Expected row not found"):
        table.assert_table_contains([{"id": 3, "name": "Charlie"}])
