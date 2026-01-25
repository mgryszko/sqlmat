import duckdb
import pytest

from sqlmat import Executor, Transformation
from sqlmat.adapters import DuckDBAdapter


@pytest.fixture
def adapter():
    with duckdb.connect(":memory:") as conn:
        yield DuckDBAdapter(conn)


def test_templated_transformation(adapter):
    class TemplatedTransform(Transformation):
        target_schema = "analytics"
        target_table = "users_summary"
        sql = """
        select
            user_id,
            count(*) as event_count
        from {{ source_schema }}.events
        group by user_id
        """

    adapter.execute("create schema analytics")
    adapter.execute("create schema raw")
    adapter.execute("create table raw.events (user_id integer, event_name varchar)")
    adapter.execute("insert into raw.events values (1, 'login'), (1, 'click'), (2, 'login')")

    executor = Executor(adapter)
    executor.run(TemplatedTransform(), params={"source_schema": "raw"})

    cursor = adapter.conn.execute("select * from analytics.users_summary order by user_id")
    assert cursor.fetchall() == [
        (1, 2),
        (2, 1),
    ]


def test_non_templated_transformation(adapter):
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
