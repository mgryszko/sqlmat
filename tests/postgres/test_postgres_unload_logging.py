import pathlib

import psycopg
import psycopg.errors
import pytest
from event_matchers import (
    data_unloaded,
    sql_rendered,
    unload_completed,
    unload_failed,
    unload_started,
)

from sqlmat import Unload
from sqlmat.adapters import PostgresAdapter
from sqlmat.core.events import Event
from sqlmat.test import SchemaRegistry, Table


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: psycopg.Connection, events: list[Event]) -> PostgresAdapter:
    return PostgresAdapter(conn, event_handler=events.append)


def test_unload_events(
    adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path, events: list[Event]
) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

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

    assert events == [
        unload_started(output_path, "csv"),
        sql_rendered(),
        data_unloaded(),
        unload_completed(output_path, "csv"),
    ]


def test_unload_error_events(adapter: PostgresAdapter, tmp_path: pathlib.Path, events: list[Event]) -> None:
    output_path = str(tmp_path / "output.csv")

    with pytest.raises(psycopg.errors.UndefinedTable):
        adapter.executor().run(
            Unload(
                sql="select * from nonexistent_table",
                destination=output_path,
                format="csv",
            )
        )

    assert events == [
        unload_started(output_path, "csv"),
        sql_rendered(),
        unload_failed(output_path, "csv"),
    ]
