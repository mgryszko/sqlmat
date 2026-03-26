import pathlib

import psycopg
import psycopg.errors
import pytest

from sqlmat import Unload
from sqlmat.adapters import PostgresAdapter
from sqlmat.test import Files, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: psycopg.Connection) -> PostgresAdapter:
    return PostgresAdapter(conn)


def test_unload_csv(adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

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

    Files(output_path).approve_csv(header=True, sort_columns=["user_id"])


def test_unload_csv_with_custom_options(
    adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=output_path,
            format="csv",
            options=["header", "delimiter '|'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(output_path).approve_csv(header=True, delimiter="|")


def test_unload_error_on_invalid_sql(adapter: PostgresAdapter, tmp_path: pathlib.Path) -> None:
    output_path = str(tmp_path / "output.csv")

    with pytest.raises(psycopg.errors.UndefinedTable):
        adapter.executor().run(
            Unload(
                sql="select * from nonexistent_table",
                destination=output_path,
                format="csv",
            )
        )

    assert not (tmp_path / "output.csv").exists()


def test_unload_rejects_non_csv_format(
    adapter: PostgresAdapter, registry: SchemaRegistry, src_table: Table, tmp_path: pathlib.Path
) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

    output_path = str(tmp_path / "output.parquet")

    with pytest.raises(ValueError, match="only supports CSV"):
        adapter.executor().run(
            Unload(
                sql="select user_id, event_date, event_count from {{ source_table }}",
                destination=output_path,
                format="parquet",
            ),
            template_context={"source_table": src_table.qualified_name},
        )
