import pyathena
import pytest
from env import AthenaEnv

from sqlmat import Unload, normalize_path
from sqlmat.adapters import AthenaAdapter
from sqlmat.test import AthenaTable, Files, SchemaRegistry
from sqlmat.test.table import ColumnSpec


@pytest.fixture
def unload_s3_uri(athena_env: AthenaEnv, test_function_id: str) -> str:
    return normalize_path(f"{athena_env.unload_s3_uri}/athena-unload-{test_function_id}/")


COLUMNS: ColumnSpec = [("user_id", "int"), ("event_date", "string"), ("event_count", "int")]


@pytest.fixture
def src_table(conn: pyathena.connection.Connection, registry: SchemaRegistry, schema: str, s3_table_base_uri: str) -> AthenaTable:
    return AthenaTable(conn, schema, "events", COLUMNS, s3_table_base_uri).create(registry)


def test_unload_parquet(adapter: AthenaAdapter, registry: SchemaRegistry, src_table: AthenaTable, unload_s3_uri: str) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="parquet",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(f"{unload_s3_uri}*").approve_parquet(sort_columns=["user_id"])


def test_unload_json(adapter: AthenaAdapter, registry: SchemaRegistry, src_table: AthenaTable, unload_s3_uri: str) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="json",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(f"{unload_s3_uri}*").approve_jsonl(sort_columns=["user_id"])


def test_unload_csv(adapter: AthenaAdapter, registry: SchemaRegistry, src_table: AthenaTable, unload_s3_uri: str) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="csv",
            options=["field_delimiter = ','"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(f"{unload_s3_uri}*").approve_csv(fieldnames=["user_id", "event_date", "event_count"], sort_columns=["user_id"])


def test_unload_with_options(adapter: AthenaAdapter, registry: SchemaRegistry, src_table: AthenaTable, unload_s3_uri: str) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="parquet",
            options=["compression = 'SNAPPY'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )
