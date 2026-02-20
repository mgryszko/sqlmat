from collections.abc import Generator

import psycopg
import pytest
from testcontainers.postgres import PostgresContainer

from sqlmat.test import PostgresTable, SchemaRegistry


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    with PostgresContainer("postgres:17") as pg:
        yield pg


@pytest.fixture
def conn(postgres_container: PostgresContainer) -> Generator[psycopg.Connection]:
    c = psycopg.connect(
        host=postgres_container.get_container_host_ip(),
        port=int(postgres_container.get_exposed_port(5432)),
        user=postgres_container.username,
        password=postgres_container.password,
        dbname=postgres_container.dbname,
    )
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture
def registry(conn: psycopg.Connection) -> Generator[SchemaRegistry]:
    r = SchemaRegistry(conn)
    yield r
    r.teardown()


@pytest.fixture
def schema(registry: SchemaRegistry) -> str:
    return registry.create_schema(prefix="test")


@pytest.fixture
def src_table(conn: psycopg.Connection, registry: SchemaRegistry, schema: str) -> PostgresTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return PostgresTable(conn, schema, "events", columns).create(registry)


@pytest.fixture
def tgt_table(conn: psycopg.Connection, registry: SchemaRegistry, schema: str) -> PostgresTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return PostgresTable(conn, schema, "daily_stats", columns).create(registry)
