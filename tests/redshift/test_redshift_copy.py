import pytest
import redshift_connector
from env import RedshiftEnv
from test.test_files import write_csv_s3, write_jsonl_s3, write_parquet_s3

from sqlmat import Copy, Executor
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import RedshiftTable, SchemaRegistry


@pytest.fixture
def adapter(conn: redshift_connector.Connection) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def executor(adapter: RedshiftAdapter) -> Executor:
    return Executor(adapter)


@pytest.fixture
def copy_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return f"{redshift_env.copy_s3_uri}/redshift-copy-{test_function_id}/"


COLUMNS = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]

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
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.parquet"
    write_parquet_s3(s3_path, PARQUET_ROWS)

    class ParquetCopy(Copy):
        source = s3_path
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    executor.run(ParquetCopy())

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
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
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    write_parquet_s3(f"{copy_s3_uri}part1.parquet", [{"user_id": 1, "event_date": "2024-01-01", "event_count": 5}])
    write_parquet_s3(f"{copy_s3_uri}part2.parquet", [{"user_id": 2, "event_date": "2024-01-02", "event_count": 3}])

    class MultiParquetCopy(Copy):
        source = copy_s3_uri
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    executor.run(MultiParquetCopy())

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
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
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.csv"
    write_csv_s3(s3_path, CSV_ROWS)

    class CsvCopy(Copy):
        source = s3_path
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'", "IGNOREHEADER 1"]

    executor.run(CsvCopy())

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
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
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.json"
    write_jsonl_s3(s3_path, PARQUET_ROWS)

    class JsonCopy(Copy):
        source = s3_path
        target_schema = schema
        target_table = "imported"
        format = "json"
        columns = COLUMNS
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    executor.run(JsonCopy())

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
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
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    old_path = f"{copy_s3_uri}old.parquet"
    write_parquet_s3(old_path, [{"user_id": 99, "event_date": "2024-01-01", "event_count": 0}])

    class FirstCopy(Copy):
        source = old_path
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    executor.run(FirstCopy())

    new_path = f"{copy_s3_uri}new.parquet"
    write_parquet_s3(new_path, PARQUET_ROWS)

    class SecondCopy(Copy):
        source = new_path
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    executor.run(SecondCopy())

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
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
    redshift_env: RedshiftEnv,
) -> None:
    class NocolsCopy(Copy):
        source = f"{copy_s3_uri}data.parquet"
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    with pytest.raises(ValueError, match="Redshift adapter requires columns"):
        executor.run(NocolsCopy())
