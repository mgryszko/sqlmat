from collections.abc import Generator

import pyathena
import pytest
from env import AthenaEnv

from sqlmat.adapters import AthenaAdapter
from sqlmat.core.events import Event
from sqlmat.core.executor import Executor
from sqlmat import normalize_path
from sqlmat.test import AthenaTable, SchemaRegistry
from sqlmat.test.table import ColumnSpec


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
def s3_table_base_uri(athena_env: AthenaEnv, test_function_id: str) -> str:
    return normalize_path(f"{athena_env.s3_table_base_uri}/sqlmat_{test_function_id}")


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: pyathena.connection.Connection, s3_table_base_uri: str, events: list[Event]) -> AthenaAdapter:
    return AthenaAdapter(conn, s3_table_base_uri=s3_table_base_uri, event_handler=events.append)


@pytest.fixture
def executor(adapter: AthenaAdapter, events: list[Event]) -> Executor:
    return Executor(adapter, event_handler=events.append)


@pytest.fixture
def registry(conn: pyathena.connection.Connection) -> Generator[SchemaRegistry]:
    with SchemaRegistry(conn) as r:
        yield r


@pytest.fixture
def schema(registry: SchemaRegistry, athena_env: AthenaEnv) -> str:
    return registry.create_schema(prefix=athena_env.schema_prefix)


@pytest.fixture
def src_table(conn: pyathena.connection.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> AthenaTable:
    columns: ColumnSpec = [("user_id", "int"), ("event_date", "date"), ("event_count", "int")]
    return AthenaTable(conn, schema, "events", columns, s3_table_base_uri).create(registry)


@pytest.fixture
def tgt_table(conn: pyathena.connection.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> AthenaTable:
    columns: ColumnSpec = [("user_id", "int"), ("event_date", "date"), ("event_count", "int")]
    return AthenaTable(conn, schema, "daily_stats", columns, s3_table_base_uri).create(registry)
