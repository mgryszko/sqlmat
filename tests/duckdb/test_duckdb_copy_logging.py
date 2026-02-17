import pathlib

import duckdb
import polars as pl
import pytest
from event_matchers import (
    copy_completed,
    copy_failed,
    copy_started,
    data_loaded,
    table_dropped,
    transaction_begun,
    transaction_committed,
    transaction_rolled_back,
)

from sqlmat import Copy, Executor
from sqlmat.adapters import DuckDBAdapter
from sqlmat.core.events import Event
from sqlmat.test import SchemaRegistry


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: duckdb.DuckDBPyConnection, events: list[Event]) -> DuckDBAdapter:
    return DuckDBAdapter(conn, event_handler=events.append)


@pytest.fixture
def executor(adapter: DuckDBAdapter, events: list[Event]) -> Executor:
    return Executor(adapter, event_handler=events.append)


def test_copy_events(executor: Executor, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path, events: list[Event]) -> None:
    path = str(tmp_path / "data.parquet")
    pl.DataFrame([{"user_id": 1, "event_count": 5}]).write_parquet(path)

    class ParquetCopy(Copy):
        source = path
        target_schema = schema
        target_table = "imported"
        format = "parquet"

    executor.run(ParquetCopy())

    assert events == [
        copy_started(path, schema, "imported", "parquet"),
        transaction_begun(),
        table_dropped(schema, "imported"),
        data_loaded(),
        transaction_committed(),
        copy_completed(path, schema, "imported", "parquet"),
    ]


def test_copy_error_events(executor: Executor, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path, events: list[Event]) -> None:
    missing_path = str(tmp_path / "nonexistent.parquet")

    class MissingFileCopy(Copy):
        source = missing_path
        target_schema = schema
        target_table = "imported"
        format = "parquet"

    with pytest.raises(duckdb.IOException):
        executor.run(MissingFileCopy())

    assert events == [
        copy_started(missing_path, schema, "imported", "parquet"),
        transaction_begun(),
        table_dropped(schema, "imported"),
        transaction_rolled_back(),
        copy_failed(missing_path, schema, "imported", "parquet"),
    ]
