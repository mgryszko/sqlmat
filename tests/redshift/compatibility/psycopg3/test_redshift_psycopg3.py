import datetime

import psycopg
import psycopg.errors
import pytest
from env import RedshiftEnv
from test.test_files import write_parquet_s3

from sqlmat import Copy, Executor, FullRefreshTableTransformation, IncrementalTableTransformation, Unload
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import Files, RedshiftTable, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: psycopg.Connection) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def executor(adapter: RedshiftAdapter) -> Executor:
    return Executor(adapter)


PARQUET_ROWS = [
    {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
    {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
]


def test_full_refresh(
    conn: psycopg.Connection, executor: Executor, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (1, "2024-01-02", 3), (2, "2024-01-01", 7)])

    class TemplatedTransform(FullRefreshTableTransformation):
        target_schema = tgt_table.schema
        target_table = tgt_table.name
        sql = """
        select
            user_id,
            max(event_date) as event_date,
            sum(event_count) as event_count
        from {{ source_table }}
        group by user_id
        """

    executor.run(TemplatedTransform(), template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 8},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 7},
        ],
        order_by=["user_id"],
    )


def test_delete_insert_single_unique_key(
    conn: psycopg.Connection, executor: Executor, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20)])

    class DeleteInsertTransform(IncrementalTableTransformation):
        target_schema = tgt_table.schema
        target_table = tgt_table.name
        strategy = "delete_insert"
        unique_key = "user_id"
        sql = "select user_id, max(event_date) as event_date, sum(event_count) as event_count from {{ source_table }} group by user_id"

    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-03", 30)])
    executor.run(DeleteInsertTransform(), template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
        ],
        order_by=["user_id"],
    )


def test_delete_insert_composite_unique_key(
    conn: psycopg.Connection, executor: Executor, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20), (1, "2024-01-02", 15), (2, "2024-01-02", 25)])
    src_table.insert([(1, "2024-01-02", 16), (2, "2024-01-02", 26), (1, "2024-01-03", 30), (2, "2024-01-03", 35)])

    class DeleteInsertTransform(IncrementalTableTransformation):
        target_schema = tgt_table.schema
        target_table = tgt_table.name
        strategy = "delete_insert"
        unique_key = ["user_id", "event_date"]
        sql = "select user_id, event_date, event_count from {{ source_table }}"

    executor.run(DeleteInsertTransform(), template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 16},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 20},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 26},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 3), "event_count": 35},
        ],
        order_by=["user_id", "event_date"],
    )


def test_delete_insert_target_table_does_not_exist(
    conn: psycopg.Connection, adapter: RedshiftAdapter, executor: Executor, src_table: Table, tgt_table: Table
) -> None:
    conn.cursor().execute(f"drop table if exists {tgt_table.qualified_name}")
    src_table.insert([(1, "2024-01-01", 10), (2, "2024-01-02", 20)])

    class DeleteInsertTransform(IncrementalTableTransformation):
        target_schema = tgt_table.schema
        target_table = tgt_table.name
        strategy = "delete_insert"
        unique_key = "user_id"
        sql = "select user_id, event_date, event_count from {{ source_table }}"

    executor.run(DeleteInsertTransform(), template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 20},
        ],
        order_by=["user_id"],
    )

    assert not adapter.table_exists(tgt_table.schema, f"{tgt_table.name}_tmp")


def test_merge(
    conn: psycopg.Connection, executor: Executor, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20)])

    class MergeTransform(IncrementalTableTransformation):
        target_schema = tgt_table.schema
        target_table = tgt_table.name
        strategy = "merge"
        unique_key = "user_id"
        sql = "select user_id, max(event_date) as event_date, sum(event_count) as event_count from {{ source_table }} group by user_id"

    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-03", 30)])
    executor.run(MergeTransform(), template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
        ],
        order_by=["user_id"],
    )


def test_full_refresh_rollback_on_error(
    conn: psycopg.Connection, adapter: RedshiftAdapter, executor: Executor, registry: SchemaRegistry, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 100)])

    class FailingTransform(FullRefreshTableTransformation):
        target_schema = tgt_table.schema
        target_table = tgt_table.name
        sql = "select * from nonexistent_table"

    with pytest.raises(psycopg.errors.UndefinedTable):
        executor.run(FailingTransform())

    assert adapter.table_exists(tgt_table.schema, tgt_table.name)
    tgt_table.assert_table_equals([{"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 100}])


def test_copy_parquet(
    executor: Executor,
    conn: psycopg.Connection,
    registry: SchemaRegistry,
    schema: str,
    copy_s3_uri: str,
    redshift_env: RedshiftEnv,
) -> None:
    s3_path = f"{copy_s3_uri}data.parquet"
    write_parquet_s3(s3_path, PARQUET_ROWS)

    copy_columns = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]

    class ParquetCopy(Copy):
        source = s3_path
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = copy_columns
        options = [f"IAM_ROLE '{redshift_env.copy_iam_role}'"]

    executor.run(ParquetCopy())

    RedshiftTable(conn, schema, "imported", copy_columns).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_unload_parquet(
    executor: Executor, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class ParquetUnload(Unload):
        sql = "select user_id, event_date, event_count from {{ source_table }}"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{redshift_env.unload_iam_role}'"]

    executor.run(ParquetUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_parquet(sort_columns=["user_id"])
