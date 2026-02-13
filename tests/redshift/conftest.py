import os
from collections.abc import Generator

import pytest
import redshift_connector
from dotenv import load_dotenv

from sqlmat.test import SchemaRegistry, Table

load_dotenv()

REDSHIFT_HOST = os.environ.get("REDSHIFT_HOST")
REDSHIFT_PORT = int(os.environ.get("REDSHIFT_PORT", "5439"))
REDSHIFT_DATABASE = os.environ.get("REDSHIFT_DATABASE")
REDSHIFT_USER = os.environ.get("REDSHIFT_USER")
REDSHIFT_PASSWORD = os.environ.get("REDSHIFT_PASSWORD")
REDSHIFT_SRC_SCHEMA_PREFIX = os.environ.get("REDSHIFT_SRC_SCHEMA_PREFIX")
REDSHIFT_TGT_SCHEMA_PREFIX = os.environ.get("REDSHIFT_TGT_SCHEMA_PREFIX")

REQUIRED_VARS = {
    "REDSHIFT_HOST": REDSHIFT_HOST,
    "REDSHIFT_DATABASE": REDSHIFT_DATABASE,
    "REDSHIFT_USER": REDSHIFT_USER,
    "REDSHIFT_PASSWORD": REDSHIFT_PASSWORD,
    "REDSHIFT_SRC_SCHEMA_PREFIX": REDSHIFT_SRC_SCHEMA_PREFIX,
    "REDSHIFT_TGT_SCHEMA_PREFIX": REDSHIFT_TGT_SCHEMA_PREFIX,
}


@pytest.fixture(autouse=True)
def require_redshift_env():
    missing = [name for name, value in REQUIRED_VARS.items() if not value]
    if missing:
        pytest.fail(f"Missing environment variables: {', '.join(missing)}")


@pytest.fixture(scope="module")
def conn() -> Generator:
    redshift_connector.paramstyle = "qmark"
    c = redshift_connector.connect(
        host=REDSHIFT_HOST,
        port=REDSHIFT_PORT,
        database=REDSHIFT_DATABASE,
        user=REDSHIFT_USER,
        password=REDSHIFT_PASSWORD,
    )
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture
def registry(conn) -> Generator[SchemaRegistry]:
    r = SchemaRegistry(conn)
    yield r
    r.teardown()


@pytest.fixture
def src_schema(registry: SchemaRegistry) -> str:
    return registry.create_schema(prefix=REDSHIFT_SRC_SCHEMA_PREFIX)


@pytest.fixture
def tgt_schema(registry: SchemaRegistry) -> str:
    return registry.create_schema(prefix=REDSHIFT_TGT_SCHEMA_PREFIX)


@pytest.fixture
def src_table(conn, registry, src_schema) -> Table:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return Table(conn, src_schema, "events", columns).create(registry)


@pytest.fixture
def tgt_table(conn, registry, tgt_schema) -> Table:
    columns = [("user_id", "integer"), ("event_date", "date"), ("event_count", "integer")]
    return Table(conn, tgt_schema, "daily_stats", columns).create(registry)
