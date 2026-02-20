import csv
import pathlib

import psycopg
import pytest

from sqlmat import Copy, Executor
from sqlmat.adapters import PostgresAdapter
from sqlmat.test import PostgresTable, SchemaRegistry


@pytest.fixture
def adapter(conn: psycopg.Connection) -> PostgresAdapter:
    return PostgresAdapter(conn)


@pytest.fixture
def executor(adapter: PostgresAdapter) -> Executor:
    return Executor(adapter)


ROWS = [
    {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
    {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
]

COLUMNS = [("user_id", "bigint"), ("event_date", "varchar"), ("event_count", "bigint")]


def test_copy_csv(executor: Executor, conn: psycopg.Connection, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "event_date", "event_count"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(ROWS)

    class CsvCopy(Copy):
        source = str(path)
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = ["header"]

    executor.run(CsvCopy())

    PostgresTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_csv_with_options(
    executor: Executor, conn: psycopg.Connection, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path
) -> None:
    path = tmp_path / "data.csv"
    with open(path, "w") as f:
        f.write("1|2024-01-01|5\n")
        f.write("2|2024-01-02|3\n")

    class PipeCsvCopy(Copy):
        source = str(path)
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = ["delimiter '|'"]

    executor.run(PipeCsvCopy())

    PostgresTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_overwrites_existing_table(
    executor: Executor, conn: psycopg.Connection, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path
) -> None:
    old_path = tmp_path / "old.csv"
    with open(old_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "event_date", "event_count"], lineterminator="\n")
        writer.writeheader()
        writer.writerow({"user_id": 99, "event_date": "2023-01-01", "event_count": 0})

    class FirstCopy(Copy):
        source = str(old_path)
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = ["header"]

    executor.run(FirstCopy())

    new_path = tmp_path / "new.csv"
    with open(new_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "event_date", "event_count"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(ROWS)

    class SecondCopy(Copy):
        source = str(new_path)
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS
        options = ["header"]

    executor.run(SecondCopy())

    PostgresTable(conn, schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_error_on_missing_file(executor: Executor, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path) -> None:
    class MissingFileCopy(Copy):
        source = str(tmp_path / "nonexistent.csv")
        target_schema = schema
        target_table = "imported"
        format = "csv"
        columns = COLUMNS

    with pytest.raises(FileNotFoundError):
        executor.run(MissingFileCopy())


def test_copy_requires_columns(executor: Executor, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("user_id,event_date,event_count\n1,2024-01-01,5\n")

    class NoColumnsCopy(Copy):
        source = str(path)
        target_schema = schema
        target_table = "imported"
        format = "csv"

    with pytest.raises(ValueError, match="requires columns"):
        executor.run(NoColumnsCopy())


def test_copy_rejects_non_csv_format(executor: Executor, registry: SchemaRegistry, schema: str, tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.parquet"
    path.write_bytes(b"fake")

    class ParquetCopy(Copy):
        source = str(path)
        target_schema = schema
        target_table = "imported"
        format = "parquet"
        columns = COLUMNS

    with pytest.raises(ValueError, match="only supports CSV"):
        executor.run(ParquetCopy())
