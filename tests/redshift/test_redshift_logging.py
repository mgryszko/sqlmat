import pytest
import redshift_connector
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

from sqlmat import Executor, FullRefreshTableTransformation, IncrementalTableTransformation
from sqlmat.adapters import RedshiftAdapter


@pytest.fixture
def events() -> list:
    return []


@pytest.fixture
def adapter(conn, events) -> RedshiftAdapter:
    return RedshiftAdapter(conn, event_handler=events.append)


@pytest.fixture
def executor(adapter, events) -> Executor:
    return Executor(adapter, event_handler=events.append)


def test_full_refresh_events(executor, tgt_schema, events):
    class Transform(FullRefreshTableTransformation):
        target_schema = tgt_schema
        target_table = "result"
        sql = "select 1 as id"

    executor.run(Transform())

    assert events == [
        table_transformation_started(tgt_schema, "result"),
        sql_rendered(tgt_schema, "result"),
        transaction_begun(),
        table_dropped(tgt_schema, "result"),
        table_created(tgt_schema, "result"),
        transaction_committed(),
        table_transformation_completed(tgt_schema, "result"),
    ]


def test_delete_insert_events(executor, tgt_schema, tgt_table, events):
    tgt_table.insert([(1, "2024-01-01", 10)])

    class Transform(IncrementalTableTransformation):
        target_schema = tgt_schema
        target_table = tgt_table.name
        strategy = "delete_insert"
        unique_key = "user_id"
        sql = "select 1 as user_id, '2024-01-01'::date as event_date, 10 as event_count"

    executor.run(Transform())

    assert events == [
        table_transformation_started(tgt_schema, tgt_table.name),
        sql_rendered(tgt_schema, tgt_table.name),
        transaction_begun(),
        table_dropped(tgt_schema, f"{tgt_table.name}_tmp"),
        table_created(tgt_schema, f"{tgt_table.name}_tmp"),
        table_existence_checked(tgt_schema, tgt_table.name),
        rows_deleted(tgt_schema, tgt_table.name),
        rows_inserted(tgt_schema, tgt_table.name),
        table_dropped(tgt_schema, f"{tgt_table.name}_tmp"),
        transaction_committed(),
        table_transformation_completed(tgt_schema, tgt_table.name),
    ]


def test_merge_events(executor, tgt_schema, tgt_table, events):
    tgt_table.insert([(1, "2024-01-01", 10)])

    class Transform(IncrementalTableTransformation):
        target_schema = tgt_schema
        target_table = tgt_table.name
        strategy = "merge"
        unique_key = "user_id"
        sql = "select 1 as user_id, '2024-01-01'::date as event_date, 10 as event_count"

    executor.run(Transform())

    assert events == [
        table_transformation_started(tgt_schema, tgt_table.name),
        sql_rendered(tgt_schema, tgt_table.name),
        transaction_begun(),
        table_dropped(tgt_schema, f"{tgt_table.name}_tmp"),
        table_created(tgt_schema, f"{tgt_table.name}_tmp"),
        table_existence_checked(tgt_schema, tgt_table.name),
        rows_merged(tgt_schema, tgt_table.name),
        table_dropped(tgt_schema, f"{tgt_table.name}_tmp"),
        transaction_committed(),
        table_transformation_completed(tgt_schema, tgt_table.name),
    ]


def test_rollback_events(executor, tgt_schema, events):
    class Transform(FullRefreshTableTransformation):
        target_schema = tgt_schema
        target_table = "result"
        sql = "select * from nonexistent_table"

    with pytest.raises(redshift_connector.error.ProgrammingError):
        executor.run(Transform())

    assert events == [
        table_transformation_started(tgt_schema, "result"),
        sql_rendered(tgt_schema, "result"),
        transaction_begun(),
        table_dropped(tgt_schema, "result"),
        table_created(tgt_schema, "result"),
        transaction_rolled_back(),
        table_transformation_failed(tgt_schema, "result"),
    ]
