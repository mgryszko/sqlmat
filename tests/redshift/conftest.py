from collections.abc import Generator

import pytest
import redshift_connector
from env import RedshiftEnv

from sqlmat.test import RedshiftTable, SchemaRegistry


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
    r = SchemaRegistry(conn)
    yield r
    r.teardown()


@pytest.fixture
def schema(registry: SchemaRegistry, redshift_env: RedshiftEnv) -> str:
    return registry.create_schema(prefix=redshift_env.schema_prefix)


@pytest.fixture
def src_table(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> RedshiftTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return RedshiftTable(conn, schema, "events", columns).create(registry)


@pytest.fixture
def tgt_table(conn: redshift_connector.Connection, registry: SchemaRegistry, schema: str) -> RedshiftTable:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return RedshiftTable(conn, schema, "daily_stats", columns).create(registry)
