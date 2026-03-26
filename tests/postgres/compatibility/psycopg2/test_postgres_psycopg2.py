import csv
import datetime
import pathlib

import psycopg2
import psycopg2.errors
import pytest

from sqlmat import Copy, FullRefreshTableTransformation, IncrementalTableTransformation, Unload
from sqlmat.adapters import PostgresAdapter
from sqlmat.test import Files, PostgresTable, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: psycopg2.extensions.connection) -> PostgresAdapter:
    return PostgresAdapter(conn)


def test_full_refresh(
    conn: psycopg2.extensions.connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (1, "2024-01-02", 3), (2, "2024-01-01", 7)])

    adapter.executor().run(
        FullRefreshTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            sql="""
        select
            user_id,
            max(event_date) as event_date,
            sum(event_count) as event_count
        from {{ source_table }}
        group by user_id
        """,
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 8},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 7},
        ],
        order_by=["user_id"],
    )


def test_delete_insert_single_unique_key(
    conn: psycopg2.extensions.connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20)])

    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-03", 30)])
    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="delete_insert",
            unique_key="user_id",
            sql="select user_id, max(event_date) as event_date, sum(event_count) as event_count from {{ source_table }} group by user_id",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
        ],
        order_by=["user_id"],
    )


def test_delete_insert_composite_unique_key(
    conn: psycopg2.extensions.connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20), (1, "2024-01-02", 15), (2, "2024-01-02", 25)])
    src_table.insert([(1, "2024-01-02", 16), (2, "2024-01-02", 26), (1, "2024-01-03", 30), (2, "2024-01-03", 35)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="delete_insert",
            unique_key=["user_id", "event_date"],
            sql="select user_id, event_date, event_count from {{ source_table }}",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

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
    conn: psycopg2.extensions.connection, adapter: PostgresAdapter, src_table: Table, tgt_table: Table
) -> None:
    conn.cursor().execute(f"drop table if exists {tgt_table.qualified_name}")
    src_table.insert([(1, "2024-01-01", 10), (2, "2024-01-02", 20)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="delete_insert",
            unique_key="user_id",
            sql="select user_id, event_date, event_count from {{ source_table }}",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 20},
        ],
        order_by=["user_id"],
    )

    assert not adapter.table_exists(tgt_table.schema, f"{tgt_table.name}_tmp")


def test_merge(
    conn: psycopg2.extensions.connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20)])

    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-03", 30)])
    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="merge",
            unique_key="user_id",
            sql="select user_id, max(event_date) as event_date, sum(event_count) as event_count from {{ source_table }} group by user_id",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
        ],
        order_by=["user_id"],
    )


def test_full_refresh_rollback_on_error(
    conn: psycopg2.extensions.connection, adapter: PostgresAdapter, registry: SchemaRegistry, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 100)])

    with pytest.raises(psycopg2.errors.UndefinedTable):
        adapter.executor().run(
            FullRefreshTableTransformation(
                target_schema=tgt_table.schema,
                target_table=tgt_table.name,
                sql="select * from nonexistent_table",
            )
        )

    assert adapter.table_exists(tgt_table.schema, tgt_table.name)
    tgt_table.assert_table_equals([{"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 100}])


def test_copy_csv(
    adapter: PostgresAdapter, conn: psycopg2.extensions.connection, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path
) -> None:
    path = tmp_path / "data.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "event_date", "event_count"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
                {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
            ]
        )

    copy_columns = [("user_id", "bigint"), ("event_date", "varchar"), ("event_count", "bigint")]

    adapter.executor().run(
        Copy(
            source=str(path),
            target_schema=schema,
            target_table="imported",
            format="csv",
            columns=copy_columns,
            options=["header"],
        )
    )

    PostgresTable(conn, schema, "imported", copy_columns).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_unload_csv(adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="csv",
            options=["header"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_csv(header=True, sort_columns=["user_id"])
