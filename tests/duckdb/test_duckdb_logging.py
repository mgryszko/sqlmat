import duckdb
import pytest
from event_matchers import (
    rows_deleted,
    rows_inserted,
    rows_merged,
    sql_rendered,
    table_created,
    table_dropped,
    table_existence_checked,
    table_transformation_completed,
    table_transformation_failed,
    table_transformation_started,
    transaction_begun,
    transaction_committed,
    transaction_rolled_back,
)

from sqlmat import FullRefreshTableTransformation, IncrementalTableTransformation
from sqlmat.adapters import DuckDBAdapter
from sqlmat.core.events import Event
from sqlmat.test import Table


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: duckdb.DuckDBPyConnection, events: list[Event]) -> DuckDBAdapter:
    return DuckDBAdapter(conn, event_handler=events.append)


def test_full_refresh_events(adapter: DuckDBAdapter, schema: str, events: list[Event]) -> None:
    adapter.executor().run(FullRefreshTableTransformation(target_schema=schema, target_table="result", sql="select 1 as id"))

    assert events == [
        table_transformation_started(schema, "result"),
        sql_rendered(schema, "result"),
        transaction_begun(),
        table_dropped(schema, "result"),
        table_created(schema, "result"),
        transaction_committed(),
        table_transformation_completed(schema, "result"),
    ]


def test_delete_insert_events(adapter: DuckDBAdapter, schema: str, tgt_table: Table, events: list[Event]) -> None:
    tgt_table.insert([(1, "2024-01-01", 10)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=schema,
            target_table=tgt_table.name,
            strategy="delete_insert",
            unique_key="user_id",
            sql="select 1 as user_id, '2024-01-01'::date as event_date, 10 as event_count",
        )
    )

    assert events == [
        table_transformation_started(schema, tgt_table.name),
        sql_rendered(schema, tgt_table.name),
        transaction_begun(),
        table_dropped(schema, f"{tgt_table.name}_tmp"),
        table_created(schema, f"{tgt_table.name}_tmp"),
        table_existence_checked(schema, tgt_table.name),
        rows_deleted(schema, tgt_table.name),
        rows_inserted(schema, tgt_table.name),
        table_dropped(schema, f"{tgt_table.name}_tmp"),
        transaction_committed(),
        table_transformation_completed(schema, tgt_table.name),
    ]


def test_merge_events(adapter: DuckDBAdapter, schema: str, tgt_table: Table, events: list[Event]) -> None:
    tgt_table.insert([(1, "2024-01-01", 10)])

    adapter.executor().run(
        IncrementalTableTransformation(
            target_schema=schema,
            target_table=tgt_table.name,
            strategy="merge",
            unique_key="user_id",
            sql="select 1 as user_id, '2024-01-01'::date as event_date, 10 as event_count",
        )
    )

    assert events == [
        table_transformation_started(schema, tgt_table.name),
        sql_rendered(schema, tgt_table.name),
        transaction_begun(),
        table_dropped(schema, f"{tgt_table.name}_tmp"),
        table_created(schema, f"{tgt_table.name}_tmp"),
        table_existence_checked(schema, tgt_table.name),
        rows_merged(schema, tgt_table.name),
        table_dropped(schema, f"{tgt_table.name}_tmp"),
        transaction_committed(),
        table_transformation_completed(schema, tgt_table.name),
    ]


def test_rollback_events(adapter: DuckDBAdapter, schema: str, events: list[Event]) -> None:
    with pytest.raises(duckdb.CatalogException):
        adapter.executor().run(
            FullRefreshTableTransformation(target_schema=schema, target_table="result", sql="select * from nonexistent_table")
        )

    assert events == [
        table_transformation_started(schema, "result"),
        sql_rendered(schema, "result"),
        transaction_begun(),
        table_dropped(schema, "result"),
        table_created(schema, "result"),
        transaction_rolled_back(),
        table_transformation_failed(schema, "result"),
    ]
