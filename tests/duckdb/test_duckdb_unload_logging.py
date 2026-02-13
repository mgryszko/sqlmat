import duckdb
import pytest
from event_matchers import (
    data_unloaded,
    sql_rendered,
    unload_completed,
    unload_failed,
    unload_started,
)

from sqlmat import Executor, Unload
from sqlmat.adapters import DuckDBAdapter


@pytest.fixture
def events() -> list:
    return []


@pytest.fixture
def adapter(conn, events) -> DuckDBAdapter:
    return DuckDBAdapter(conn, event_handler=events.append)


@pytest.fixture
def executor(adapter, events) -> Executor:
    return Executor(adapter, event_handler=events.append)


def test_unload_events(executor, registry, src_table, tmp_path, events):
    src_table.insert([(1, "2024-01-01", 5)])

    output_path = str(tmp_path / "output.parquet")

    class ParquetUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "parquet"

    executor.run(ParquetUnload(), template_context={"source_table": src_table.qualified_name})

    assert events == [
        unload_started(output_path, "parquet"),
        sql_rendered(),
        data_unloaded(),
        unload_completed(output_path, "parquet"),
    ]


def test_unload_error_events(executor, tmp_path, events):
    output_path = str(tmp_path / "output.parquet")

    class BadUnload(Unload):
        sql = "select * from nonexistent_table"
        destination = output_path
        format = "parquet"

    with pytest.raises(duckdb.CatalogException):
        executor.run(BadUnload())

    assert events == [
        unload_started(output_path, "parquet"),
        sql_rendered(),
        unload_failed(output_path, "parquet"),
    ]
