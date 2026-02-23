import pyathena
import pytest
from env import AthenaEnv
from test.test_files import write_csv_s3, write_jsonl_s3, write_parquet_s3

from sqlmat import Copy, Executor
from sqlmat import normalize_path
from sqlmat.test import AthenaTable, SchemaRegistry
from sqlmat.test.table import ColumnSpec


@pytest.fixture
def copy_s3_uri(athena_env: AthenaEnv, test_function_id: str) -> str:
    return normalize_path(f"{athena_env.copy_s3_uri}/athena-copy-{test_function_id}/")


COLUMNS: ColumnSpec = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]

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
    conn: pyathena.connection.Connection,
    registry: SchemaRegistry,
    schema: str,
    s3_table_base_uri: str,
    copy_s3_uri: str,
) -> None:
    s3_path = f"{copy_s3_uri}data.parquet"
    write_parquet_s3(s3_path, PARQUET_ROWS)

    class ParquetCopy(Copy):
        source = copy_s3_uri
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS

    executor.run(ParquetCopy())

    AthenaTable(conn, schema, "imported", COLUMNS, s3_table_base_uri).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_csv(
    executor: Executor,
    conn: pyathena.connection.Connection,
    registry: SchemaRegistry,
    schema: str,
    s3_table_base_uri: str,
    copy_s3_uri: str,
) -> None:
    s3_path = f"{copy_s3_uri}data.csv"
    write_csv_s3(s3_path, CSV_ROWS)

    class CsvCopy(Copy):
        source = copy_s3_uri
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = ["'skip.header.line.count'='1'"]

    executor.run(CsvCopy())

    AthenaTable(conn, schema, "imported", COLUMNS, s3_table_base_uri).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_json(
    executor: Executor,
    conn: pyathena.connection.Connection,
    registry: SchemaRegistry,
    schema: str,
    s3_table_base_uri: str,
    copy_s3_uri: str,
) -> None:
    s3_path = f"{copy_s3_uri}data.json"
    write_jsonl_s3(s3_path, PARQUET_ROWS)

    class JsonCopy(Copy):
        source = copy_s3_uri
        target_schema = schema
        target_table = "imported"
        format = "json"
        columns = COLUMNS

    executor.run(JsonCopy())

    AthenaTable(conn, schema, "imported", COLUMNS, s3_table_base_uri).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_overwrites_existing_table(
    executor: Executor,
    conn: pyathena.connection.Connection,
    registry: SchemaRegistry,
    schema: str,
    s3_table_base_uri: str,
    copy_s3_uri: str,
) -> None:
    old_uri = f"{copy_s3_uri}old/"
    write_parquet_s3(f"{old_uri}data.parquet", [{"user_id": 99, "event_date": "2024-01-01", "event_count": 0}])

    class FirstCopy(Copy):
        source = old_uri
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS

    executor.run(FirstCopy())

    new_uri = f"{copy_s3_uri}new/"
    write_parquet_s3(f"{new_uri}data.parquet", PARQUET_ROWS)

    class SecondCopy(Copy):
        source = new_uri
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS

    executor.run(SecondCopy())

    AthenaTable(conn, schema, "imported", COLUMNS, s3_table_base_uri).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_requires_columns(
    executor: Executor,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
) -> None:
    class NocolsCopy(Copy):
        source = f"{copy_s3_uri}data.parquet"
        target_schema = schema
        target_table = "imported"
        format = "parquet"

    with pytest.raises(ValueError, match="Athena adapter requires columns"):
        executor.run(NocolsCopy())
