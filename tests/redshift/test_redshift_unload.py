import pytest
import redshift_connector
from env import RedshiftEnv

from sqlmat import Executor, Unload
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import Files, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: redshift_connector.Connection) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def executor(adapter: RedshiftAdapter) -> Executor:
    return Executor(adapter)


@pytest.fixture
def unload_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return f"{redshift_env.unload_s3_uri}/redshift-unload-{test_function_id}/"


def test_unload_parquet(
    executor: Executor, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class ParquetUnload(Unload):
        sql = "select user_id, event_date, event_count from {{ source_table }}"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{redshift_env.unload_iam_role}'"]

    executor.run(ParquetUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_parquet(sort_columns=["user_id"])


def test_unload_csv(executor: Executor, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class CsvUnload(Unload):
        sql = "select user_id, event_date, event_count from {{ source_table }}"
        destination = unload_s3_uri
        format = "csv"
        options = [f"IAM_ROLE '{redshift_env.unload_iam_role}'", "HEADER"]

    executor.run(CsvUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_csv(header=True, sort_columns=["user_id"])


def test_unload_json(executor: Executor, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    class JsonUnload(Unload):
        sql = "select user_id, event_date, event_count from {{ source_table }}"
        destination = unload_s3_uri
        format = "json"
        options = [f"IAM_ROLE '{redshift_env.unload_iam_role}'"]

    executor.run(JsonUnload(), template_context={"source_table": src_table.qualified_name})

    Files(f"{unload_s3_uri}*").approve_jsonl(sort_columns=["user_id"])


def test_unload_with_options(
    executor: Executor, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

    class OptionsUnload(Unload):
        sql = "select user_id, event_date, event_count from {{ source_table }}"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{redshift_env.unload_iam_role}'", "ALLOWOVERWRITE"]

    executor.run(OptionsUnload(), template_context={"source_table": src_table.qualified_name})


def test_unload_error_on_invalid_sql(executor: Executor, unload_s3_uri: str, redshift_env: RedshiftEnv) -> None:
    class BadUnload(Unload):
        sql = "select * from nonexistent_table"
        destination = unload_s3_uri
        format = "parquet"
        options = [f"IAM_ROLE '{redshift_env.unload_iam_role}'"]

    with pytest.raises(redshift_connector.error.ProgrammingError):
        executor.run(BadUnload())
