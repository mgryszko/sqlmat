from datetime import date

import pyathena
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
    table_transformation_started,
    transaction_begun,
    transaction_committed,
)

from sqlmat import Executor, FullRefreshTableTransformation, IncrementalTableTransformation
from sqlmat.adapters import AthenaAdapter
from sqlmat.core.events import Event
from sqlmat.test import Table


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: pyathena.connection.Connection, s3_table_base_uri: str, events: list[Event]) -> AthenaAdapter:
    return AthenaAdapter(conn, s3_table_base_uri=s3_table_base_uri, event_handler=events.append)


@pytest.fixture
def executor(adapter: AthenaAdapter, events: list[Event]) -> Executor:
    return Executor(adapter, event_handler=events.append)


def test_full_refresh_events(executor: Executor, schema: str, events: list[Event]) -> None:
    executor.run(
        FullRefreshTableTransformation(
            target_schema=schema,
            target_table="result",
            sql="select 1 as id",
        ),
    )

    assert events == [
        table_transformation_started(schema, "result"),
        sql_rendered(schema, "result"),
        transaction_begun(),
        table_dropped(schema, "result"),
        table_created(schema, "result"),
        transaction_committed(),
        table_transformation_completed(schema, "result"),
    ]


def test_delete_insert_events(executor: Executor, schema: str, tgt_table: Table, events: list[Event]) -> None:
    tgt_table.insert([(1, date(2024, 1, 1), 10)])

    executor.run(
        IncrementalTableTransformation(
            target_schema=schema,
            target_table=tgt_table.name,
            sql="select 1 as user_id, date '2024-01-01' as event_date, 10 as event_count",
            strategy="delete_insert",
            unique_key="user_id",
        ),
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


def test_merge_events(executor: Executor, schema: str, tgt_table: Table, events: list[Event]) -> None:
    tgt_table.insert([(1, date(2024, 1, 1), 10)])

    executor.run(
        IncrementalTableTransformation(
            target_schema=schema,
            target_table=tgt_table.name,
            sql="select 1 as user_id, date '2024-01-01' as event_date, 10 as event_count",
            strategy="merge",
            unique_key="user_id",
        ),
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
