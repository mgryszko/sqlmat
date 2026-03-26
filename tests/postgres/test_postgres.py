import datetime

import psycopg
import psycopg.errors
import pytest

from sqlmat import FullRefreshTableTransformation, IncrementalTableTransformation
from sqlmat.adapters import TARGET_TABLE_ALIAS, PostgresAdapter
from sqlmat.test import SchemaRegistry, Table


@pytest.fixture
def adapter(conn: psycopg.Connection) -> PostgresAdapter:
    return PostgresAdapter(conn)


def test_full_refresh_templated(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
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


def test_full_refresh_non_templated(conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, tgt_table: Table) -> None:
    adapter.executor().run(
        FullRefreshTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            sql="select 42 as user_id, '2024-01-01'::date as event_date, 100 as event_count",
        )
    )

    tgt_table.assert_table_equals([{"user_id": 42, "event_date": datetime.date(2024, 1, 1), "event_count": 100}])


def test_delete_insert_single_unique_key(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    executor = adapter.executor()
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20)])

    transformation = IncrementalTableTransformation(
        target_schema=tgt_table.schema,
        target_table=tgt_table.name,
        strategy="delete_insert",
        unique_key="user_id",
        sql="select user_id, max(event_date) as event_date, sum(event_count) as event_count from {{ source_table }} group by user_id",
    )

    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-03", 30)])
    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
        ],
        order_by=["user_id"],
    )

    src_table.delete()
    src_table.insert([(3, "2024-01-03", 35), (4, "2024-01-04", 40)])
    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 35},
            {"user_id": 4, "event_date": datetime.date(2024, 1, 4), "event_count": 40},
        ],
        order_by=["user_id"],
    )


def test_delete_insert_composite_unique_key(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    executor = adapter.executor()
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20), (1, "2024-01-02", 15), (2, "2024-01-02", 25)])
    src_table.insert([(1, "2024-01-02", 16), (2, "2024-01-02", 26), (1, "2024-01-03", 30), (2, "2024-01-03", 35)])

    transformation = IncrementalTableTransformation(
        target_schema=tgt_table.schema,
        target_table=tgt_table.name,
        strategy="delete_insert",
        unique_key=["user_id", "event_date"],
        sql="select user_id, event_date, event_count from {{ source_table }}",
    )

    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

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

    src_table.delete()
    src_table.insert([(1, "2024-01-03", 31), (2, "2024-01-03", 36), (1, "2024-01-04", 40), (2, "2024-01-04", 45)])
    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 16},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 3), "event_count": 31},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 4), "event_count": 40},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 20},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 26},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 3), "event_count": 36},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 4), "event_count": 45},
        ],
        order_by=["user_id", "event_date"],
    )


def test_delete_insert_with_incremental_predicates_single_string(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-02", 30)])
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 16), (3, "2024-01-01", 5)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="delete_insert",
            unique_key="user_id",
            incremental_predicates=f"{TARGET_TABLE_ALIAS}.event_count > 15",
            sql="select user_id, event_date, event_count from {{ source_table }}",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 1), "event_count": 5},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 2), "event_count": 30},
        ],
        order_by=["user_id", "event_date"],
    )


def test_delete_insert_with_incremental_predicates_list(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    src_table.insert([(1, "2024-01-02", 16), (2, "2024-01-02", 26)])
    tgt_table.insert([(1, "2024-01-01", 5), (1, "2024-01-02", 15), (2, "2024-01-01", 8), (2, "2024-01-02", 15)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="delete_insert",
            unique_key=["user_id", "event_date"],
            incremental_predicates=[f"{TARGET_TABLE_ALIAS}.event_date >= '2024-01-02'", f"{TARGET_TABLE_ALIAS}.event_count > 10"],
            sql="select user_id, event_date, event_count from {{ source_table }}",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 5},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 16},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 8},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 26},
        ],
        order_by=["user_id", "event_date"],
    )


def test_delete_insert_target_table_does_not_exist(
    conn: psycopg.Connection, adapter: PostgresAdapter, src_table: Table, tgt_table: Table
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


def test_delete_insert_without_unique_key_raises_error(adapter: PostgresAdapter, schema: str, src_table: Table) -> None:
    src_table.insert([(1, "2024-01-01", 10), (2, "2024-01-02", 20)])

    with pytest.raises(ValueError, match="unique_key is required for delete_insert materialization"):
        adapter.executor().run(
            IncrementalTableTransformation(
                target_schema=schema,
                target_table="bad_incremental",
                strategy="delete_insert",
                sql="select user_id, event_date, event_count from {{ source_table }}",
            ),
            template_context={"source_table": src_table.qualified_name},
        )


def test_merge_single_unique_key(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    executor = adapter.executor()
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20)])

    transformation = IncrementalTableTransformation(
        target_schema=tgt_table.schema,
        target_table=tgt_table.name,
        strategy="merge",
        unique_key="user_id",
        sql="select user_id, max(event_date) as event_date, sum(event_count) as event_count from {{ source_table }} group by user_id",
    )

    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-03", 30)])
    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 30},
        ],
        order_by=["user_id"],
    )

    src_table.delete()
    src_table.insert([(3, "2024-01-03", 35), (4, "2024-01-04", 40)])
    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 3), "event_count": 35},
            {"user_id": 4, "event_date": datetime.date(2024, 1, 4), "event_count": 40},
        ],
        order_by=["user_id"],
    )


def test_merge_composite_unique_key(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    executor = adapter.executor()
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 20), (1, "2024-01-02", 15), (2, "2024-01-02", 25)])
    src_table.insert([(1, "2024-01-02", 16), (2, "2024-01-02", 26), (1, "2024-01-03", 30), (2, "2024-01-03", 35)])

    transformation = IncrementalTableTransformation(
        target_schema=tgt_table.schema,
        target_table=tgt_table.name,
        strategy="merge",
        unique_key=["user_id", "event_date"],
        sql="select user_id, event_date, event_count from {{ source_table }}",
    )

    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

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

    src_table.delete()
    src_table.insert([(1, "2024-01-03", 31), (2, "2024-01-03", 36), (1, "2024-01-04", 40), (2, "2024-01-04", 45)])
    executor.run(transformation, template_context={"source_table": src_table.qualified_name})

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 16},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 3), "event_count": 31},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 4), "event_count": 40},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 20},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 26},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 3), "event_count": 36},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 4), "event_count": 45},
        ],
        order_by=["user_id", "event_date"],
    )


def test_merge_with_incremental_predicates_single_string(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    src_table.insert([(2, "2024-01-02", 25), (3, "2024-01-02", 30)])
    tgt_table.insert([(1, "2024-01-01", 10), (2, "2024-01-01", 16), (3, "2024-01-01", 5)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="merge",
            unique_key="user_id",
            incremental_predicates=f"{TARGET_TABLE_ALIAS}.event_count > 15",
            sql="select user_id, event_date, event_count from {{ source_table }}",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 10},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 25},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 1), "event_count": 5},
            {"user_id": 3, "event_date": datetime.date(2024, 1, 2), "event_count": 30},
        ],
        order_by=["user_id", "event_date"],
    )


def test_merge_with_incremental_predicates_list(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tgt_table: Table
) -> None:
    src_table.insert([(1, "2024-01-02", 16), (2, "2024-01-02", 26)])
    tgt_table.insert([(1, "2024-01-01", 5), (1, "2024-01-02", 15), (2, "2024-01-01", 8), (2, "2024-01-02", 15)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="merge",
            unique_key=["user_id", "event_date"],
            incremental_predicates=[f"{TARGET_TABLE_ALIAS}.event_date >= '2024-01-02'", f"{TARGET_TABLE_ALIAS}.event_count > 10"],
            sql="select user_id, event_date, event_count from {{ source_table }}",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    tgt_table.assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 5},
            {"user_id": 1, "event_date": datetime.date(2024, 1, 2), "event_count": 16},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 1), "event_count": 8},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 26},
        ],
        order_by=["user_id", "event_date"],
    )


def test_merge_target_table_does_not_exist(conn: psycopg.Connection, adapter: PostgresAdapter, src_table: Table, tgt_table: Table) -> None:
    src_table.insert([(1, "2024-01-01", 10), (2, "2024-01-02", 20)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=tgt_table.schema,
            target_table=tgt_table.name,
            strategy="merge",
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


def test_merge_without_unique_key_raises_error(adapter: PostgresAdapter, src_table: Table) -> None:
    src_table.insert([(1, "2024-01-01", 10), (2, "2024-01-02", 20)])

    with pytest.raises(ValueError, match="unique_key is required for merge materialization"):
        adapter.executor().run(
            IncrementalTableTransformation(
                target_schema=src_table.schema,
                target_table="bad_merge",
                strategy="merge",
                sql="select user_id, event_date, event_count from {{ source_table }}",
            ),
            template_context={"source_table": src_table.qualified_name},
        )


def test_full_refresh_rollback_on_error(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 100)])

    with pytest.raises(psycopg.errors.UndefinedTable):
        adapter.executor().run(
            FullRefreshTableTransformation(
                target_schema=tgt_table.schema,
                target_table=tgt_table.name,
                sql="select * from nonexistent_table",
            )
        )

    assert adapter.table_exists(tgt_table.schema, tgt_table.name)
    tgt_table.assert_table_equals([{"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 100}])


def test_delete_insert_rollback_on_error(
    conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, tgt_table: Table
) -> None:
    tgt_table.insert([(1, "2024-01-01", 100)])

    with pytest.raises(psycopg.errors.UndefinedTable):
        adapter.executor().run(
            IncrementalTableTransformation(
                target_schema=tgt_table.schema,
                target_table=tgt_table.name,
                strategy="delete_insert",
                unique_key="user_id",
                sql="select * from nonexistent_table",
            )
        )

    assert adapter.table_exists(tgt_table.schema, tgt_table.name)
    tgt_table.assert_table_equals([{"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 100}])
    assert not adapter.table_exists(tgt_table.schema, f"{tgt_table.name}_tmp")


def test_merge_rollback_on_error(conn: psycopg.Connection, adapter: PostgresAdapter, registry: SchemaRegistry, tgt_table: Table) -> None:
    tgt_table.insert([(1, "2024-01-01", 100)])

    with pytest.raises(psycopg.errors.UndefinedTable):
        adapter.executor().run(
            IncrementalTableTransformation(
                target_schema=tgt_table.schema,
                target_table=tgt_table.name,
                strategy="merge",
                unique_key="user_id",
                sql="select * from nonexistent_table",
            )
        )

    assert adapter.table_exists(tgt_table.schema, tgt_table.name)
    tgt_table.assert_table_equals([{"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 100}])
    assert not adapter.table_exists(tgt_table.schema, f"{tgt_table.name}_tmp")
