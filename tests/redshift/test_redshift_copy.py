import os

import pytest
import redshift_connector
from dotenv import load_dotenv
from test.test_files import write_csv_s3, write_jsonl_s3, write_parquet_s3

from sqlmat import Copy, Executor
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import SchemaRegistry, Table

load_dotenv()

COPY_S3_URI = os.environ.get("COPY_S3_URI")
REDSHIFT_COPY_IAM_ROLE = os.environ.get("REDSHIFT_COPY_IAM_ROLE")

REQUIRED_VARS = {
    "COPY_S3_URI": COPY_S3_URI,
    "REDSHIFT_COPY_IAM_ROLE": REDSHIFT_COPY_IAM_ROLE,
}

COLUMNS = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]


@pytest.fixture(autouse=True)
def require_copy_env() -> None:
    missing = [name for name, value in REQUIRED_VARS.items() if not value]
    if missing:
        pytest.fail(f"Missing environment variables: {', '.join(missing)}")


@pytest.fixture
def adapter(conn: redshift_connector.Connection) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def executor(adapter: RedshiftAdapter) -> Executor:
    return Executor(adapter)


@pytest.fixture
def copy_s3_uri(test_function_id: str) -> str:
    return f"{COPY_S3_URI}/redshift-copy-{test_function_id}/"


PARQUET_ROWS = [
    {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
    {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
]

CSV_ROWS = [
    {"user_id": "1", "event_date": "2024-01-01", "event_count": "5"},
    {"user_id": "2", "event_date": "2024-01-02", "event_count": "3"},
]


def test_copy_parquet(
    executor: Executor,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    tgt_schema: str,
    copy_s3_uri: str,
) -> None:
    s3_path = f"{copy_s3_uri}data.parquet"
    write_parquet_s3(s3_path, PARQUET_ROWS)

    class ParquetCopy(Copy):
        source = s3_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    executor.run(ParquetCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_multiple_parquet_files(
    executor: Executor,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    tgt_schema: str,
    copy_s3_uri: str,
) -> None:
    write_parquet_s3(f"{copy_s3_uri}part1.parquet", [{"user_id": 1, "event_date": "2024-01-01", "event_count": 5}])
    write_parquet_s3(f"{copy_s3_uri}part2.parquet", [{"user_id": 2, "event_date": "2024-01-02", "event_count": 3}])

    class MultiParquetCopy(Copy):
        source = copy_s3_uri
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    executor.run(MultiParquetCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_csv(
    executor: Executor,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    tgt_schema: str,
    copy_s3_uri: str,
) -> None:
    s3_path = f"{copy_s3_uri}data.csv"
    write_csv_s3(s3_path, CSV_ROWS)

    class CsvCopy(Copy):
        source = s3_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'", "IGNOREHEADER 1"]

    executor.run(CsvCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_json(
    executor: Executor,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    tgt_schema: str,
    copy_s3_uri: str,
) -> None:
    s3_path = f"{copy_s3_uri}data.json"
    write_jsonl_s3(s3_path, PARQUET_ROWS)

    class JsonCopy(Copy):
        source = s3_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "json"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    executor.run(JsonCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_overwrites_existing_table(
    executor: Executor,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    tgt_schema: str,
    copy_s3_uri: str,
) -> None:
    old_path = f"{copy_s3_uri}old.parquet"
    write_parquet_s3(old_path, [{"user_id": 99, "event_date": "2024-01-01", "event_count": 0}])

    class FirstCopy(Copy):
        source = old_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    executor.run(FirstCopy())

    new_path = f"{copy_s3_uri}new.parquet"
    write_parquet_s3(new_path, PARQUET_ROWS)

    class SecondCopy(Copy):
        source = new_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    executor.run(SecondCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_requires_columns(
    executor: Executor,
    registry: SchemaRegistry,
    tgt_schema: str,
    copy_s3_uri: str,
) -> None:
    class NocolsCopy(Copy):
        source = f"{copy_s3_uri}data.parquet"
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"
        options = [f"IAM_ROLE '{REDSHIFT_COPY_IAM_ROLE}'"]

    with pytest.raises(ValueError, match="Redshift adapter requires columns"):
        executor.run(NocolsCopy())
