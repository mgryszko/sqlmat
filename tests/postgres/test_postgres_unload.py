import pathlib

import psycopg
import psycopg.errors
import pytest

from sqlmat import Executor, Unload
from sqlmat.adapters import PostgresAdapter
from sqlmat.test import Files, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: psycopg.Connection) -> PostgresAdapter:
    return PostgresAdapter(conn)


@pytest.fixture
def executor(adapter: PostgresAdapter) -> Executor:
    return Executor(adapter)


def test_unload_csv(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="csv",
            options=["header"],
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
            options=["header", "delimiter '|'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_csv(header=True, delimiter="|")


def test_unload_error_on_invalid_sql(executor: Executor, tmp_path: pathlib.Path) -> None:
    output_path = str(tmp_path / "output.csv")

    with pytest.raises(psycopg.errors.UndefinedTable):
        executor.run(
            Unload(
                sql="select * from nonexistent_table",
                destination=output_path,
                format="csv",
            )
        )

    assert not (tmp_path / "output.csv").exists()


def test_unload_rejects_non_csv_format(executor: Executor, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

    output_path = str(tmp_path / "output.parquet")

    with pytest.raises(ValueError, match="only supports CSV"):
        executor.run(
            Unload(
                sql="select user_id, event_date, event_count from {{ source_table }}",
                destination=output_path,
                format="parquet",
            ),
            template_context={"source_table": src_table.qualified_name},
        )
