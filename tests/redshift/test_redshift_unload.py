import os

import pytest
import redshift_connector
from dotenv import load_dotenv

from sqlmat import Executor, Unload
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import Files

load_dotenv()

UNLOAD_S3_URI = os.environ.get("UNLOAD_S3_URI")
REDSHIFT_UNLOAD_IAM_ROLE = os.environ.get("REDSHIFT_UNLOAD_IAM_ROLE")

REQUIRED_VARS = {
    "UNLOAD_S3_URI": UNLOAD_S3_URI,
    "REDSHIFT_UNLOAD_IAM_ROLE": REDSHIFT_UNLOAD_IAM_ROLE,
}


@pytest.fixture(autouse=True)
def require_redshift_env():
    missing = [name for name, value in REQUIRED_VARS.items() if not value]
    if missing:
        pytest.fail(f"Missing environment variables: {', '.join(missing)}")


@pytest.fixture
def adapter(conn) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def executor(adapter) -> Executor:
    return Executor(adapter)


@pytest.fixture
def unload_s3_uri(test_function_id: str) -> str:
    return f"{UNLOAD_S3_URI}/redshift-unload-{test_function_id}/"


def test_unload_parquet(executor, registry, src_table, unload_s3_uri):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class ParquetUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'"]

    executor.run(ParquetUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_parquet(sort_columns=["user_id"])


def test_unload_csv(executor, registry, src_table, unload_s3_uri):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class CsvUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = unload_s3_uri
        format = "csv"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'", "HEADER"]

    executor.run(CsvUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_csv(header=True, sort_columns=["user_id"])


def test_unload_json(executor, registry, src_table, unload_s3_uri):
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class JsonUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = unload_s3_uri
        format = "json"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'"]

    executor.run(JsonUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_jsonl(sort_columns=["user_id"])


def test_unload_with_options(executor, registry, src_table, unload_s3_uri):
    src_table.insert([(1, "2024-01-01", 5)])

    class OptionsUnload(Unload):
        sql = "select * from {{ source_table }}"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'", "ALLOWOVERWRITE"]

    executor.run(OptionsUnload(), template_context={"source_table": src_table.qualified_name})


def test_unload_error_on_invalid_sql(executor, unload_s3_uri):
    class BadUnload(Unload):
        sql = "select * from nonexistent_table"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{REDSHIFT_UNLOAD_IAM_ROLE}'"]

    with pytest.raises(redshift_connector.error.ProgrammingError):
        executor.run(BadUnload())
