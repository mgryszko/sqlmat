from collections.abc import Generator

import psycopg2
import pytest
from env import RedshiftEnv

from sqlmat import normalize_path
from sqlmat.test import RedshiftTable, SchemaRegistry


@pytest.fixture(scope="module")
def conn(redshift_env: RedshiftEnv) -> Generator[psycopg2.extensions.connection]:
    c = psycopg2.connect(
        host=redshift_env.host,
        port=redshift_env.port,
        dbname=redshift_env.database,
        user=redshift_env.user,
        password=redshift_env.password,
        client_encoding="utf8",
    )
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture
def registry(conn: psycopg2.extensions.connection) -> Generator[SchemaRegistry]:
    with SchemaRegistry(conn) as r:
        yield r


@pytest.fixture
def schema(registry: SchemaRegistry, redshift_env: RedshiftEnv) -> str:
    return registry.create_schema(prefix=redshift_env.schema_prefix)


@pytest.fixture
def src_table(conn: psycopg2.extensions.connection, registry: SchemaRegistry, schema: str) -> RedshiftTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return RedshiftTable(conn, schema, "events", columns).create(registry)


@pytest.fixture
def tgt_table(conn: psycopg2.extensions.connection, registry: SchemaRegistry, schema: str) -> RedshiftTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return RedshiftTable(conn, schema, "daily_stats", columns).create(registry)


@pytest.fixture
def copy_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return normalize_path(f"{redshift_env.copy_s3_uri}/redshift-copy-{test_function_id}/")


@pytest.fixture
def unload_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return normalize_path(f"{redshift_env.unload_s3_uri}/redshift-unload-{test_function_id}/")
