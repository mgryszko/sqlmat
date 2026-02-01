import datetime
from collections.abc import Generator

import duckdb
import pytest

from sqlmat import Executor, Transformation
from sqlmat.adapters import DuckDBAdapter


@pytest.fixture
def adapter() -> Generator[DuckDBAdapter]:
    with duckdb.connect(":memory:") as conn:
        yield DuckDBAdapter(conn)


def test_full_refresh_templated(adapter: DuckDBAdapter):
    class TemplatedTransform(Transformation):
        target_schema = "analytics"
        target_table = "users_summary"
        sql = """
        select
            user_id,
            sum(event_count) as total_events
        from {{ source_schema }}.events
        group by user_id
        """

    adapter.execute("create schema analytics")
    adapter.execute("create schema staging")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-01', 5), (1, '2024-01-02', 3), (2, '2024-01-01', 7)")

    executor = Executor(adapter)
    executor.run(TemplatedTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.users_summary order by user_id")
    assert cursor.fetchall() == [
        (1, 8),
        (2, 7),
    ]


def test_full_refresh_non_templated(adapter: DuckDBAdapter):
    class NonTemplatedTransform(Transformation):
        target_schema = "analytics"
        target_table = "simple_result"
        sql = "select 42 as id, 'test' as name"

    adapter.execute("create schema analytics")

    executor = Executor(adapter)
    executor.run(NonTemplatedTransform())

    cursor = adapter.conn.execute("select * from analytics.simple_result")
    assert cursor.fetchall() == [
        (42, "test"),
    ]


def test_delete_insert_single_unique_key(adapter: DuckDBAdapter):
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "delete_insert"
        unique_key = "user_id"
        sql = "select user_id, sum(event_count) as event_count from {{ source_schema }}.events group by user_id"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_count integer)")
    adapter.execute("insert into analytics.daily_stats values (1, 10), (2, 20)")

    executor = Executor(adapter)

    # First transformation: update user_id=2, add user_id=3
    adapter.execute("insert into staging.events values (2, '2024-01-02', 25), (3, '2024-01-03', 30)")
    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id")
    assert cursor.fetchall() == [(1, 10), (2, 25), (3, 30)]

    # Second transformation: update user_id=3, add user_id=4
    adapter.execute("delete from staging.events")
    adapter.execute("insert into staging.events values (3, '2024-01-03', 35), (4, '2024-01-04', 40)")
    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id")
    assert cursor.fetchall() == [(1, 10), (2, 25), (3, 35), (4, 40)]


def test_delete_insert_composite_unique_key(adapter: DuckDBAdapter):
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "delete_insert"
        unique_key = ["user_id", "event_date"]
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_date date, event_count integer)")
    adapter.execute(
        "insert into analytics.daily_stats values "
        "(1, '2024-01-01', 10), (2, '2024-01-01', 20), (1, '2024-01-02', 15), (2, '2024-01-02', 25)"
    )

    executor = Executor(adapter)

    # First transformation: update 2024-01-02, add 2024-01-03
    adapter.execute(
        "insert into staging.events values "
        "(1, '2024-01-02', 16), (2, '2024-01-02', 26), (1, '2024-01-03', 30), (2, '2024-01-03', 35)"
    )
    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (1, datetime.date(2024, 1, 2), 16),
        (1, datetime.date(2024, 1, 3), 30),
        (2, datetime.date(2024, 1, 1), 20),
        (2, datetime.date(2024, 1, 2), 26),
        (2, datetime.date(2024, 1, 3), 35),
    ]

    # Second transformation: update 2024-01-03, add 2024-01-04
    adapter.execute("delete from staging.events")
    adapter.execute(
        "insert into staging.events values "
        "(1, '2024-01-03', 31), (2, '2024-01-03', 36), (1, '2024-01-04', 40), (2, '2024-01-04', 45)"
    )
    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (1, datetime.date(2024, 1, 2), 16),
        (1, datetime.date(2024, 1, 3), 31),
        (1, datetime.date(2024, 1, 4), 40),
        (2, datetime.date(2024, 1, 1), 20),
        (2, datetime.date(2024, 1, 2), 26),
        (2, datetime.date(2024, 1, 3), 36),
        (2, datetime.date(2024, 1, 4), 45),
    ]


def test_delete_insert_target_table_does_not_exist(adapter: DuckDBAdapter):
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "new_table"
        materialization = "delete_insert"
        unique_key = "user_id"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema analytics")
    adapter.execute("create schema staging")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-01', 10), (2, '2024-01-02', 20)")

    executor = Executor(adapter)
    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.new_table order by user_id")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (2, datetime.date(2024, 1, 2), 20),
    ]

    temp_exists = adapter.table_exists("analytics", "new_table_tmp")
    assert not temp_exists


def test_delete_insert_without_unique_key_raises_error(adapter: DuckDBAdapter):
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "bad_incremental"
        materialization = "delete_insert"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema analytics")
    adapter.execute("create schema staging")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-01', 10), (2, '2024-01-02', 20)")

    executor = Executor(adapter)

    with pytest.raises(ValueError, match="unique_key is required for delete_insert materialization"):
        executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})
