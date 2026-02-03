import datetime
from collections.abc import Generator

import duckdb
import pytest

from sqlmat import Executor, Transformation
from sqlmat.adapters import TARGET_TABLE_ALIAS, DuckDBAdapter


@pytest.fixture
def adapter() -> Generator[DuckDBAdapter]:
    with duckdb.connect(":memory:") as conn:
        yield DuckDBAdapter(conn)


@pytest.fixture
def executor(adapter: DuckDBAdapter) -> Executor:
    return Executor(adapter)


def test_full_refresh_templated(adapter: DuckDBAdapter, executor: Executor):
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

    executor.run(TemplatedTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.users_summary order by user_id")
    assert cursor.fetchall() == [
        (1, 8),
        (2, 7),
    ]


def test_full_refresh_non_templated(adapter: DuckDBAdapter, executor: Executor):
    class NonTemplatedTransform(Transformation):
        target_schema = "analytics"
        target_table = "simple_result"
        sql = "select 42 as id, 'test' as name"

    adapter.execute("create schema analytics")

    executor.run(NonTemplatedTransform())

    cursor = adapter.conn.execute("select * from analytics.simple_result")
    assert cursor.fetchall() == [
        (42, "test"),
    ]


def test_delete_insert_single_unique_key(adapter: DuckDBAdapter, executor: Executor):
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


def test_delete_insert_composite_unique_key(adapter: DuckDBAdapter, executor: Executor):
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
    adapter.execute(
        "insert into staging.events values (1, '2024-01-02', 16), (2, '2024-01-02', 26), (1, '2024-01-03', 30), (2, '2024-01-03', 35)"
    )

    # First transformation: update 2024-01-02, add 2024-01-03
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
        "insert into staging.events values (1, '2024-01-03', 31), (2, '2024-01-03', 36), (1, '2024-01-04', 40), (2, '2024-01-04', 45)"
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


def test_delete_insert_with_incremental_predicates_single_string(adapter: DuckDBAdapter, executor: Executor) -> None:
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "delete_insert"
        unique_key = "user_id"
        incremental_predicates = f"{TARGET_TABLE_ALIAS}.event_count > 15"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (2, '2024-01-02', 25), (3, '2024-01-02', 30)")
    adapter.execute("insert into analytics.daily_stats values (1, '2024-01-01', 10), (2, '2024-01-01', 16), (3, '2024-01-01', 5)")

    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (2, datetime.date(2024, 1, 2), 25),
        (3, datetime.date(2024, 1, 1), 5),
        (3, datetime.date(2024, 1, 2), 30),
    ]


def test_delete_insert_with_incremental_predicates_list(adapter: DuckDBAdapter, executor: Executor) -> None:
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "delete_insert"
        unique_key = ["user_id", "event_date"]
        incremental_predicates = [f"{TARGET_TABLE_ALIAS}.event_date >= '2024-01-02'", f"{TARGET_TABLE_ALIAS}.event_count > 10"]
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-02', 16), (2, '2024-01-02', 26)")
    adapter.execute(
        "insert into analytics.daily_stats values (1, '2024-01-01', 5), (1, '2024-01-02', 15), (2, '2024-01-01', 8), (2, '2024-01-02', 15)"
    )

    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 5),
        (1, datetime.date(2024, 1, 2), 16),
        (2, datetime.date(2024, 1, 1), 8),
        (2, datetime.date(2024, 1, 2), 26),
    ]


def test_delete_insert_target_table_does_not_exist(adapter: DuckDBAdapter, executor: Executor):
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

    executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.new_table order by user_id")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (2, datetime.date(2024, 1, 2), 20),
    ]

    temp_exists = adapter.table_exists("analytics", "new_table_tmp")
    assert not temp_exists


def test_delete_insert_without_unique_key_raises_error(adapter: DuckDBAdapter, executor: Executor):
    class DeleteInsertTransform(Transformation):
        target_schema = "analytics"
        target_table = "bad_incremental"
        materialization = "delete_insert"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema analytics")
    adapter.execute("create schema staging")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-01', 10), (2, '2024-01-02', 20)")

    with pytest.raises(ValueError, match="unique_key is required for delete_insert materialization"):
        executor.run(DeleteInsertTransform(), params={"source_schema": "staging"})


def test_merge_single_unique_key(adapter: DuckDBAdapter, executor: Executor):
    class MergeTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "merge"
        unique_key = "user_id"
        sql = "select user_id, sum(event_count) as event_count from {{ source_schema }}.events group by user_id"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_count integer)")
    adapter.execute("insert into analytics.daily_stats values (1, 10), (2, 20)")

    adapter.execute("insert into staging.events values (2, '2024-01-02', 25), (3, '2024-01-03', 30)")
    executor.run(MergeTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id")
    assert cursor.fetchall() == [(1, 10), (2, 25), (3, 30)]

    adapter.execute("delete from staging.events")
    adapter.execute("insert into staging.events values (3, '2024-01-03', 35), (4, '2024-01-04', 40)")
    executor.run(MergeTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id")
    assert cursor.fetchall() == [(1, 10), (2, 25), (3, 35), (4, 40)]


def test_merge_composite_unique_key(adapter: DuckDBAdapter, executor: Executor):
    class MergeTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "merge"
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
    adapter.execute(
        "insert into staging.events values (1, '2024-01-02', 16), (2, '2024-01-02', 26), (1, '2024-01-03', 30), (2, '2024-01-03', 35)"
    )

    executor.run(MergeTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (1, datetime.date(2024, 1, 2), 16),
        (1, datetime.date(2024, 1, 3), 30),
        (2, datetime.date(2024, 1, 1), 20),
        (2, datetime.date(2024, 1, 2), 26),
        (2, datetime.date(2024, 1, 3), 35),
    ]

    adapter.execute("delete from staging.events")
    adapter.execute(
        "insert into staging.events values (1, '2024-01-03', 31), (2, '2024-01-03', 36), (1, '2024-01-04', 40), (2, '2024-01-04', 45)"
    )
    executor.run(MergeTransform(), params={"source_schema": "staging"})

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


def test_merge_with_incremental_predicates_single_string(adapter: DuckDBAdapter, executor: Executor) -> None:
    class MergeTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "merge"
        unique_key = "user_id"
        incremental_predicates = f"{TARGET_TABLE_ALIAS}.event_count > 15"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (2, '2024-01-02', 25), (3, '2024-01-02', 30)")
    adapter.execute("insert into analytics.daily_stats values (1, '2024-01-01', 10), (2, '2024-01-01', 16), (3, '2024-01-01', 5)")

    executor.run(MergeTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (2, datetime.date(2024, 1, 2), 25),
        (3, datetime.date(2024, 1, 1), 5),
        (3, datetime.date(2024, 1, 2), 30),
    ]


def test_merge_with_incremental_predicates_list(adapter: DuckDBAdapter, executor: Executor) -> None:
    class MergeTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "merge"
        unique_key = ["user_id", "event_date"]
        incremental_predicates = [f"{TARGET_TABLE_ALIAS}.event_date >= '2024-01-02'", f"{TARGET_TABLE_ALIAS}.event_count > 10"]
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema staging")
    adapter.execute("create schema analytics")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("create table analytics.daily_stats (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-02', 16), (2, '2024-01-02', 26)")
    adapter.execute(
        "insert into analytics.daily_stats values (1, '2024-01-01', 5), (1, '2024-01-02', 15), (2, '2024-01-01', 8), (2, '2024-01-02', 15)"
    )

    executor.run(MergeTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.daily_stats order by user_id, event_date")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 5),
        (1, datetime.date(2024, 1, 2), 16),
        (2, datetime.date(2024, 1, 1), 8),
        (2, datetime.date(2024, 1, 2), 26),
    ]


def test_merge_target_table_does_not_exist(adapter: DuckDBAdapter, executor: Executor):
    class MergeTransform(Transformation):
        target_schema = "analytics"
        target_table = "new_table"
        materialization = "merge"
        unique_key = "user_id"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema analytics")
    adapter.execute("create schema staging")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-01', 10), (2, '2024-01-02', 20)")

    executor.run(MergeTransform(), params={"source_schema": "staging"})

    cursor = adapter.conn.execute("select * from analytics.new_table order by user_id")
    assert cursor.fetchall() == [
        (1, datetime.date(2024, 1, 1), 10),
        (2, datetime.date(2024, 1, 2), 20),
    ]

    temp_exists = adapter.table_exists("analytics", "new_table_tmp")
    assert not temp_exists


def test_merge_without_unique_key_raises_error(adapter: DuckDBAdapter, executor: Executor):
    class MergeTransform(Transformation):
        target_schema = "analytics"
        target_table = "bad_merge"
        materialization = "merge"
        sql = "select user_id, event_date, event_count from {{ source_schema }}.events"

    adapter.execute("create schema analytics")
    adapter.execute("create schema staging")
    adapter.execute("create table staging.events (user_id integer, event_date date, event_count integer)")
    adapter.execute("insert into staging.events values (1, '2024-01-01', 10), (2, '2024-01-02', 20)")

    with pytest.raises(ValueError, match="unique_key is required for merge materialization"):
        executor.run(MergeTransform(), params={"source_schema": "staging"})


def test_full_refresh_rollback_on_error(adapter: DuckDBAdapter, executor: Executor):
    class FailingTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        sql = "select * from nonexistent_table"

    adapter.execute("create schema analytics")
    adapter.execute("create table analytics.daily_stats (id integer, name varchar)")
    adapter.execute("insert into analytics.daily_stats values (1, 'original')")

    with pytest.raises(duckdb.CatalogException, match="nonexistent_table"):
        executor.run(FailingTransform())

    assert adapter.table_exists("analytics", "daily_stats")
    cursor = adapter.conn.execute("select * from analytics.daily_stats")
    assert cursor.fetchall() == [(1, "original")]


def test_delete_insert_rollback_on_error(adapter: DuckDBAdapter, executor: Executor):
    class FailingTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "delete_insert"
        unique_key = "id"
        sql = "select * from nonexistent_table"

    adapter.execute("create schema analytics")
    adapter.execute("create table analytics.daily_stats (id integer, name varchar)")
    adapter.execute("insert into analytics.daily_stats values (1, 'original')")

    with pytest.raises(duckdb.CatalogException, match="nonexistent_table"):
        executor.run(FailingTransform())

    assert adapter.table_exists("analytics", "daily_stats")
    cursor = adapter.conn.execute("select * from analytics.daily_stats")
    assert cursor.fetchall() == [(1, "original")]
    assert not adapter.table_exists("analytics", "daily_stats_tmp")


def test_merge_rollback_on_error(adapter: DuckDBAdapter, executor: Executor):
    class FailingTransform(Transformation):
        target_schema = "analytics"
        target_table = "daily_stats"
        materialization = "merge"
        unique_key = "id"
        sql = "select * from nonexistent_table"

    adapter.execute("create schema analytics")
    adapter.execute("create table analytics.daily_stats (id integer, name varchar)")
    adapter.execute("insert into analytics.daily_stats values (1, 'original')")

    with pytest.raises(duckdb.CatalogException, match="nonexistent_table"):
        executor.run(FailingTransform())

    assert adapter.table_exists("analytics", "daily_stats")
    cursor = adapter.conn.execute("select * from analytics.daily_stats")
    assert cursor.fetchall() == [(1, "original")]
    assert not adapter.table_exists("analytics", "daily_stats_tmp")
