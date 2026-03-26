import csv
import pathlib

import psycopg
import pytest
from event_matchers import (
    copy_completed,
    copy_failed,
    copy_started,
    data_loaded,
    table_created,
    table_dropped,
    transaction_begun,
    transaction_committed,
    transaction_rolled_back,
)

from sqlmat import Copy
from sqlmat.adapters import PostgresAdapter
from sqlmat.core.events import Event
from sqlmat.test import SchemaRegistry

COLUMNS = [("user_id", "bigint"), ("event_date", "varchar"), ("event_count", "bigint")]


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: psycopg.Connection, events: list[Event]) -> PostgresAdapter:
    return PostgresAdapter(conn, event_handler=events.append)


def test_copy_events(adapter: PostgresAdapter, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path, events: list[Event]) -> None:
    path = tmp_path / "data.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "event_date", "event_count"], lineterminator="\n")
        writer.writeheader()
        writer.writerow({"user_id": 1, "event_date": "2024-01-01", "event_count": 5})

    adapter.executor().run(
        Copy(
            source=str(path),
            target_schema=schema,
            target_table="imported",
            format="csv",
            columns=COLUMNS,
            options=["header"],
        )
    )

    assert events == [
        copy_started(str(path), schema, "imported", "csv"),
        transaction_begun(),
        table_dropped(schema, "imported"),
        table_created(schema, "imported"),
        data_loaded(),
        transaction_committed(),
        copy_completed(str(path), schema, "imported", "csv"),
    ]


def test_copy_error_events(
    adapter: PostgresAdapter, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path, events: list[Event]
) -> None:
    missing_path = str(tmp_path / "nonexistent.csv")

    with pytest.raises(FileNotFoundError):
        adapter.executor().run(
            Copy(
                source=missing_path,
                target_schema=schema,
                target_table="imported",
                format="csv",
                columns=COLUMNS,
            )
        )

    assert events == [
        copy_started(missing_path, schema, "imported", "csv"),
        transaction_begun(),
        table_dropped(schema, "imported"),
        table_created(schema, "imported"),
        transaction_rolled_back(),
        copy_failed(missing_path, schema, "imported", "csv"),
    ]
