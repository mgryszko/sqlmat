import pytest
import redshift_connector
from env import RedshiftEnv
from test.test_files import write_csv_s3, write_jsonl_s3, write_parquet_s3

from sqlmat import Copy, normalize_path
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import RedshiftTable, SchemaRegistry


@pytest.fixture
def adapter(conn: redshift_connector.Connection) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def copy_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return normalize_path(f"{redshift_env.copy_s3_uri}/redshift-copy-{test_function_id}/")


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
    adapter: RedshiftAdapter,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.parquet"
    write_parquet_s3(s3_path, PARQUET_ROWS)

    adapter.executor().run(
        Copy(
            source=s3_path,
            target_schema=schema,
            target_table="imported",
            format="parquet",
            columns=COLUMNS,
            options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'"],
        )
    )

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_multiple_parquet_files(
    adapter: RedshiftAdapter,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    write_parquet_s3(f"{copy_s3_uri}part1.parquet", [{"user_id": 1, "event_date": "2024-01-01", "event_count": 5}])
    write_parquet_s3(f"{copy_s3_uri}part2.parquet", [{"user_id": 2, "event_date": "2024-01-02", "event_count": 3}])

    adapter.executor().run(
        Copy(
            source=copy_s3_uri,
            target_schema=schema,
            target_table="imported",
            format="parquet",
            columns=COLUMNS,
            options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'"],
        )
    )

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_csv(
    adapter: RedshiftAdapter,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.csv"
    write_csv_s3(s3_path, CSV_ROWS)

    adapter.executor().run(
        Copy(
            source=s3_path,
            target_schema=schema,
            target_table="imported",
            format="csv",
            columns=COLUMNS,
            options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'", "IGNOREHEADER 1"],
        )
    )

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_json(
    adapter: RedshiftAdapter,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.json"
    write_jsonl_s3(s3_path, PARQUET_ROWS)

    adapter.executor().run(
        Copy(
            source=s3_path,
            target_schema=schema,
            target_table="imported",
            format="json",
            columns=COLUMNS,
            options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'"],
        )
    )

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_overwrites_existing_table(
    adapter: RedshiftAdapter,
    conn: redshift_connector.Connection,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    executor = adapter.executor()
    old_path = f"{copy_s3_uri}old.parquet"
    write_parquet_s3(old_path, [{"user_id": 99, "event_date": "2024-01-01", "event_count": 0}])

    executor.run(
        Copy(
            source=old_path,
            target_schema=schema,
            target_table="imported",
            format="parquet",
            columns=COLUMNS,
            options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'"],
        )
    )

    new_path = f"{copy_s3_uri}new.parquet"
    write_parquet_s3(new_path, PARQUET_ROWS)

    executor.run(
        Copy(
            source=new_path,
            target_schema=schema,
            target_table="imported",
            format="parquet",
            columns=COLUMNS,
            options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'"],
        )
    )

    RedshiftTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_requires_columns(
    adapter: RedshiftAdapter,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    with pytest.raises(ValueError, match="Redshift adapter requires columns"):
        adapter.executor().run(
            Copy(
                source=f"{copy_s3_uri}data.parquet",
                target_schema=schema,
                target_table="imported",
                format="parquet",
                options=[f"IAM_ROLE '{redshift_env.copy_iam_role}'"],
            )
        )
