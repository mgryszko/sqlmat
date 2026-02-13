import duckdb
import pytest

from sqlmat import Executor, Unload
from sqlmat.adapters import DuckDBAdapter
from sqlmat.test import Files


@pytest.fixture
def adapter(conn) -> DuckDBAdapter:
    return DuckDBAdapter(conn)


@pytest.fixture
def executor(adapter) -> Executor:
    return Executor(adapter)


def test_unload_parquet(executor, registry, src_table, tmp_path):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.parquet")

    class ParquetUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "parquet"

    executor.run(ParquetUnload(), template_context={"source_table": src_table.qualified_name})

    Files(output_path).approve_parquet(sort_columns=["user_id"])


def test_unload_csv(executor, registry, src_table, tmp_path):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    class CsvUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "csv"

    executor.run(CsvUnload(), template_context={"source_table": src_table.qualified_name})

    Files(output_path).approve_csv(header=True, sort_columns=["user_id"])


def test_unload_json(executor, registry, src_table, tmp_path):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.json")

    class JsonUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "json"

    executor.run(JsonUnload(), template_context={"source_table": src_table.qualified_name})

    Files(output_path).approve_jsonl(sort_columns=["user_id"])


def test_unload_json_with_gzip(executor, registry, src_table, tmp_path):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.json.gz")

    class JsonGzipUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "json"
        options = ["COMPRESSION gzip"]

    executor.run(JsonGzipUnload(), template_context={"source_table": src_table.qualified_name})

    Files(output_path).approve_jsonl(sort_columns=["user_id"])


def test_unload_csv_with_gzip(executor, registry, src_table, tmp_path):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv.gz")

    class CsvGzipUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "csv"
        options = ["COMPRESSION gzip"]

    executor.run(CsvGzipUnload(), template_context={"source_table": src_table.qualified_name})

    Files(output_path).approve_csv(header=True, sort_columns=["user_id"])


def test_unload_csv_with_custom_options(executor, registry, src_table, tmp_path):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    output_path = str(tmp_path / "output.csv")

    class CsvUnloadWithOptions(Unload):
        sql = "select * from {{ source_table }}"
        destination = output_path
        format = "csv"
        options = ["HEADER TRUE", "DELIMITER '|'"]

    executor.run(CsvUnloadWithOptions(), template_context={"source_table": src_table.qualified_name})

    Files(output_path).approve_csv()


def test_unload_error_on_invalid_sql(executor, tmp_path):
    output_path = str(tmp_path / "output.parquet")

    class BadUnload(Unload):
        sql = "select * from nonexistent_table"
        destination = output_path
        format = "parquet"

    with pytest.raises(duckdb.CatalogException, match="nonexistent_table"):
        executor.run(BadUnload())

    assert not (tmp_path / "output.parquet").exists()
