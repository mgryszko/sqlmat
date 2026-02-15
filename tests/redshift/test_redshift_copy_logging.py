import os

import pytest
import redshift_connector
from dotenv import load_dotenv
from event_matchers import (
    copy_completed,
    copy_failed,
    copy_started,
    data_loaded,
    table_created,
    table_dropped,
    transaction_begun,
    transaction_committed,
    transaction_rolled_back,
)
from test.test_files import write_parquet_s3

from sqlmat import Copy, Executor
from sqlmat.adapters import RedshiftAdapter
from sqlmat.core.events import Event
from sqlmat.test import SchemaRegistry

load_dotenv()

COPY_S3_URI = os.environ.get("COPY_S3_URI")
REDSHIFT_COPY_IAM_ROLE = os.environ.get("REDSHIFT_COPY_IAM_ROLE")

COLUMNS = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]


@pytest.fixture(autouse=True)
def require_copy_env() -> None:
    missing = [name for name, value in {"COPY_S3_URI": COPY_S3_URI, "REDSHIFT_COPY_IAM_ROLE": REDSHIFT_COPY_IAM_ROLE}.items() if not value]
    if missing:
        pytest.fail(f"Missing environment variables: {', '.join(missing)}")


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: redshift_connector.Connection, events: list[Event]) -> RedshiftAdapter:
    return RedshiftAdapter(conn, event_handler=events.append)


@pytest.fixture
def executor(adapter: RedshiftAdapter, events: list[Event]) -> Executor:
    return Executor(adapter, event_handler=events.append)


@pytest.fixture
def copy_s3_uri(test_function_id: str) -> str:
    return f"{COPY_S3_URI}/redshift_copy_{test_function_id}/"


def test_copy_events(executor: Executor, registry: SchemaRegistry, tgt_schema: str, copy_s3_uri: str, events: list[Event]) -> None:
    s3_path = f"{copy_s3_uri}data.parquet"
    write_parquet_s3(s3_path, [{"user_id": 1, "event_date": "2024-01-01", "event_count": 5}])

    class ParquetCopy(Copy):
        source = s3_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    executor.run(ParquetCopy())

    assert events == [
        copy_started(s3_path, tgt_schema, "imported", "parquet"),
        transaction_begun(),
        table_dropped(tgt_schema, "imported"),
        table_created(tgt_schema, "imported"),
        data_loaded(),
        transaction_committed(),
        copy_completed(s3_path, tgt_schema, "imported", "parquet"),
    ]


def test_copy_error_events(executor: Executor, registry: SchemaRegistry, tgt_schema: str, copy_s3_uri: str, events: list[Event]) -> None:
    bad_path = f"{copy_s3_uri}bad_schema.parquet"
    write_parquet_s3(bad_path, [{"wrong_col": 1}])

    class BadSchemaCopy(Copy):
        source = bad_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    with pytest.raises(redshift_connector.error.ProgrammingError):
        executor.run(BadSchemaCopy())

    assert events == [
        copy_started(bad_path, tgt_schema, "imported", "parquet"),
        transaction_begun(),
        table_dropped(tgt_schema, "imported"),
        table_created(tgt_schema, "imported"),
        transaction_rolled_back(),
        copy_failed(bad_path, tgt_schema, "imported", "parquet"),
    ]
