import csv
import json
import os
import pathlib

import polars as pl
import pytest
from fsspec import open as fsspec_open

from sqlmat.test import Files

UNLOAD_S3_URI = os.environ.get("UNLOAD_S3_URI")


@pytest.fixture(autouse=True)
def require_s3_env() -> None:
    if not UNLOAD_S3_URI:
        pytest.fail("Missing environment variable: UNLOAD_S3_URI")


@pytest.fixture
def s3_uri(test_function_id: str) -> str:
    return f"{UNLOAD_S3_URI}/files-approvals-{test_function_id}/"


FIELDNAMES = ["user_id", "event_date", "event_count"]

PART_1_CSV = [
    {"user_id": "2", "event_date": "2024-01-02", "event_count": "3"},
    {"user_id": "1", "event_date": "2024-01-02", "event_count": "7"},
]
PART_2_CSV = [
    {"user_id": "1", "event_date": "2024-01-01", "event_count": "5"},
    {"user_id": "2", "event_date": "2024-01-01", "event_count": "9"},
]

PART_1_JSON = [
    {"user_id": 2, "event_date": "2024-01-02", "event_count": 3},
    {"user_id": 1, "event_date": "2024-01-02", "event_count": 7},
]
PART_2_JSON = [
    {"user_id": 1, "event_date": "2024-01-01", "event_count": 5},
    {"user_id": 2, "event_date": "2024-01-01", "event_count": 9},
]

SORT_COLUMNS = ["user_id", "event_date"]


def write_csv(path: str | pathlib.Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_csv_s3(uri: str, rows: list[dict[str, str]]) -> None:
    with fsspec_open(uri, "w") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: str | pathlib.Path, rows: list[dict[str, object]]) -> None:
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_jsonl_s3(uri: str, rows: list[dict[str, object]]) -> None:
    with fsspec_open(uri, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_parquet(path: str | pathlib.Path, rows: list[dict[str, object]]) -> None:
    pl.DataFrame(rows).write_parquet(path)


def write_parquet_s3(uri: str, rows: list[dict[str, object]]) -> None:
    with fsspec_open(uri, "wb") as f:
        pl.DataFrame(rows).write_parquet(f)


def test_approve_csv_multiple_local_files(tmp_path: pathlib.Path) -> None:
    write_csv(tmp_path / "part1.csv", PART_1_CSV)
    write_csv(tmp_path / "part2.csv", PART_2_CSV)

    Files(f"{tmp_path}/*.csv").approve_csv(header=True, sort_columns=SORT_COLUMNS)


def test_approve_csv_multiple_s3_files(s3_uri: str) -> None:
    write_csv_s3(f"{s3_uri}part1.csv", PART_1_CSV)
    write_csv_s3(f"{s3_uri}part2.csv", PART_2_CSV)

    Files(f"{s3_uri}*.csv").approve_csv(header=True, sort_columns=SORT_COLUMNS)


def test_approve_jsonl_multiple_local_files(tmp_path: pathlib.Path) -> None:
    write_jsonl(tmp_path / "part1.json", PART_1_JSON)
    write_jsonl(tmp_path / "part2.json", PART_2_JSON)

    Files(f"{tmp_path}/*.json").approve_jsonl(sort_columns=SORT_COLUMNS)


def test_approve_jsonl_multiple_s3_files(s3_uri: str) -> None:
    write_jsonl_s3(f"{s3_uri}part1.json", PART_1_JSON)
    write_jsonl_s3(f"{s3_uri}part2.json", PART_2_JSON)

    Files(f"{s3_uri}*.json").approve_jsonl(sort_columns=SORT_COLUMNS)


def test_approve_parquet_multiple_local_files(tmp_path: pathlib.Path) -> None:
    write_parquet(tmp_path / "part1.parquet", PART_1_JSON)
    write_parquet(tmp_path / "part2.parquet", PART_2_JSON)

    Files(f"{tmp_path}/*.parquet").approve_parquet(sort_columns=SORT_COLUMNS)


def test_approve_parquet_multiple_s3_files(s3_uri: str) -> None:
    write_parquet_s3(f"{s3_uri}part1.parquet", PART_1_JSON)
    write_parquet_s3(f"{s3_uri}part2.parquet", PART_2_JSON)

    Files(f"{s3_uri}*.parquet").approve_parquet(sort_columns=SORT_COLUMNS)
