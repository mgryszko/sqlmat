import pytest
import redshift_connector
from env import RedshiftEnv

from sqlmat import Unload, normalize_path
from sqlmat.adapters import RedshiftAdapter
from sqlmat.test import Files, SchemaRegistry, Table


@pytest.fixture
def adapter(conn: redshift_connector.Connection) -> RedshiftAdapter:
    return RedshiftAdapter(conn)


@pytest.fixture
def unload_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return normalize_path(f"{redshift_env.unload_s3_uri}/redshift-unload-{test_function_id}/")


def test_unload_parquet(
    adapter: RedshiftAdapter, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="parquet",
            options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(f"{unload_s3_uri}*").approve_parquet(sort_columns=["user_id"])


def test_unload_csv(
    adapter: RedshiftAdapter, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="csv",
            options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'", "HEADER"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(f"{unload_s3_uri}*").approve_csv(header=True, sort_columns=["user_id"])


def test_unload_json(
    adapter: RedshiftAdapter, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5), (2, "2024-01-02", 3)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="json",
            options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    Files(f"{unload_s3_uri}*").approve_jsonl(sort_columns=["user_id"])


def test_unload_with_options(
    adapter: RedshiftAdapter, registry: SchemaRegistry, src_table: Table, unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

    adapter.executor().run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="parquet",
            options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'", "ALLOWOVERWRITE"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )


def test_unload_error_on_invalid_sql(adapter: RedshiftAdapter, unload_s3_uri: str, redshift_env: RedshiftEnv) -> None:
    with pytest.raises(redshift_connector.error.ProgrammingError):
        adapter.executor().run(
            Unload(
                sql="select * from nonexistent_table",
                destination=unload_s3_uri,
                format="parquet",
                options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'"],
            )
        )
