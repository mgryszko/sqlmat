import pathlib

import duckdb
import pytest

from sqlmat import Executor, Unload
from sqlmat.adapters import DuckDBAdapter
from sqlmat.test import Files, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: duckdb.DuckDBPyConnection) -> DuckDBAdapter:
    return DuckDBAdapter(conn)


@pytest.fixture
def executor(adapter: DuckDBAdapter) -> Executor:
    return Executor(adapter)


def test_unload_parquet(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.parquet")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="parquet",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_parquet(sort_columns=["user_id"])


def test_unload_csv(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="csv",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_csv(header=True, sort_columns=["user_id"])


def test_unload_json(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.json")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="json",
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_jsonl(sort_columns=["user_id"])


def test_unload_json_with_gzip(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.json.gz")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="json",
            options=["COMPRESSION gzip"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_jsonl(sort_columns=["user_id"])


def test_unload_csv_with_gzip(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv.gz")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="csv",
            options=["COMPRESSION gzip"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_csv(header=True, sort_columns=["user_id"])


def test_unload_csv_with_custom_options(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="csv",
            options=["HEADER TRUE", "DELIMITER '|'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_csv(header=True, delimiter="|")


def test_unload_error_on_invalid_sql(executor: Executor, tmp_path: pathlib.Path) -> None:
    output_path = str(tmp_path / "output.parquet")

    with pytest.raises(duckdb.CatalogException, match="nonexistent_table"):
        executor.run(
            Unload(
                sql="select * from nonexistent_table",
                destination=output_path,
                format="parquet",
            )
        )

    assert not (tmp_path / "output.parquet").exists()
