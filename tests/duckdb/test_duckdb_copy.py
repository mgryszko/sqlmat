import csv
import datetime
import json
import pathlib

import duckdb
import polars as pl
import pytest

from sqlmat import Copy, Executor
from sqlmat.adapters import DuckDBAdapter
from sqlmat.test import SchemaRegistry, Table


@pytest.fixture
def adapter(conn: duckdb.DuckDBPyConnection) -> DuckDBAdapter:
    return DuckDBAdapter(conn)


@pytest.fixture
def executor(adapter: DuckDBAdapter) -> Executor:
    return Executor(adapter)


ROWS = [
    {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
    {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
]

COLUMNS = [("user_id", "bigint"), ("event_date", "varchar"), ("event_count", "bigint")]


def test_copy_parquet(
    executor: Executor, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path
) -> None:
    path = str(tmp_path / "data.parquet")
    pl.DataFrame(ROWS).write_parquet(path)

    class ParquetCopy(Copy):
        source = path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"

    executor.run(ParquetCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_csv(
    executor: Executor, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path
) -> None:
    path = tmp_path / "data.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "event_date", "event_count"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {"user_id": "1", "event_date": "2024-01-01", "event_count": "5"},
                {"user_id": "2", "event_date": "2024-01-02", "event_count": "3"},
            ]
        )

    class CsvCopy(Copy):
        source = str(path)
        target_schema = tgt_schema
        target_table = "imported"
        format = "csv"

    executor.run(CsvCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 5},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_multiple_parquet_files(
    executor: Executor, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path
) -> None:
    pl.DataFrame([{"user_id": 1, "event_date": "2024-01-01", "event_count": 5}]).write_parquet(tmp_path / "part1.parquet")
    pl.DataFrame([{"user_id": 2, "event_date": "2024-01-02", "event_count": 3}]).write_parquet(tmp_path / "part2.parquet")
    glob_path = str(tmp_path / "*.parquet")

    class MultiFileCopy(Copy):
        source = glob_path
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"

    executor.run(MultiFileCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_json(
    executor: Executor, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path
) -> None:
    path = tmp_path / "data.json"
    with open(path, "w") as f:
        for row in ROWS:
            f.write(json.dumps(row) + "\n")

    class JsonCopy(Copy):
        source = str(path)
        target_schema = tgt_schema
        target_table = "imported"
        format = "json"

    executor.run(JsonCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": datetime.date(2024, 1, 1), "event_count": 5},
            {"user_id": 2, "event_date": datetime.date(2024, 1, 2), "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_csv_with_options(
    executor: Executor, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path
) -> None:
    path = tmp_path / "data.csv"
    with open(path, "w") as f:
        f.write("1|2024-01-01|5\n")
        f.write("2|2024-01-02|3\n")

    class PipeCsvCopy(Copy):
        source = str(path)
        target_schema = tgt_schema
        target_table = "imported"
        format = "csv"
        options = ["delim='|'", "header=false", "columns={'user_id': 'INTEGER', 'event_date': 'VARCHAR', 'event_count': 'INTEGER'}"]

    executor.run(PipeCsvCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_overwrites_existing_table(
    executor: Executor, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path
) -> None:
    path1 = str(tmp_path / "old.parquet")
    pl.DataFrame([{"user_id": 99, "event_count": 0}]).write_parquet(path1)

    class FirstCopy(Copy):
        source = path1
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"

    executor.run(FirstCopy())

    path2 = str(tmp_path / "new.parquet")
    pl.DataFrame(ROWS).write_parquet(path2)

    class SecondCopy(Copy):
        source = path2
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"

    executor.run(SecondCopy())

    Table(conn, tgt_schema, "imported", COLUMNS).assert_table_equals(
        [
            {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
            {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
        ],
        order_by=["user_id"],
    )


def test_copy_error_on_missing_file(executor: Executor, registry: SchemaRegistry, tgt_schema: str, tmp_path: pathlib.Path) -> None:
    class MissingFileCopy(Copy):
        source = str(tmp_path / "nonexistent.parquet")
        target_schema = tgt_schema
        target_table = "imported"
        format = "parquet"

    with pytest.raises(duckdb.IOException):
        executor.run(MissingFileCopy())
