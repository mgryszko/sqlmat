import os

import pytest
import redshift_connector
from dotenv import load_dotenv
from event_matchers import (
    data_unloaded,
    sql_rendered,
    unload_completed,
    unload_failed,
    unload_started,
)

from sqlmat import Executor, Unload
from sqlmat.adapters import RedshiftAdapter

load_dotenv()

UNLOAD_S3_URI = os.environ.get("UNLOAD_S3_URI")
REDSHIFT_UNLOAD_IAM_ROLE = os.environ.get("REDSHIFT_UNLOAD_IAM_ROLE")


@pytest.fixture(autouse=True)
def require_unload_env():
    missing = [
        name
        for name, value in {"UNLOAD_S3_URI": UNLOAD_S3_URI, "REDSHIFT_UNLOAD_IAM_ROLE": REDSHIFT_UNLOAD_IAM_ROLE}.items()
        if not value
    ]
    if missing:
        pytest.fail(f"Missing environment variables: {', '.join(missing)}")


@pytest.fixture
def events() -> list:
    return []


@pytest.fixture
def adapter(conn, events) -> RedshiftAdapter:
    return RedshiftAdapter(conn, event_handler=events.append)


@pytest.fixture
def executor(adapter, events) -> Executor:
    return Executor(adapter, event_handler=events.append)


@pytest.fixture
def unload_s3_uri(test_function_id: str) -> str:
    return f"{UNLOAD_S3_URI}/redshift_unload_{test_function_id}/"


def test_unload_events(executor, registry, src_table, events, unload_s3_uri):
    src_table.insert([(1, "2024-01-01", 5)])

    class ParquetUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'"]

    executor.run(ParquetUnload(), template_context={"source_table": src_table.qualified_name})

    assert events == [
        unload_started(unload_s3_uri, "parquet"),
        sql_rendered(),
        data_unloaded(),
        unload_completed(unload_s3_uri, "parquet"),
    ]


def test_unload_error_events(executor, events, unload_s3_uri):
    class BadUnload(Unload):
        sql = "select * from nonexistent_table"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'"]

    with pytest.raises(redshift_connector.error.ProgrammingError):
        executor.run(BadUnload())

    assert events == [
        unload_started(unload_s3_uri, "parquet"),
        sql_rendered(),
        unload_failed(unload_s3_uri, "parquet"),
    ]
