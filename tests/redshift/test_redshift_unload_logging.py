import pytest
import redshift_connector
from env import RedshiftEnv
from event_matchers import (
    data_unloaded,
    sql_rendered,
    unload_completed,
    unload_failed,
    unload_started,
)

from sqlmat import Executor, Unload, normalize_path
from sqlmat.adapters import RedshiftAdapter
from sqlmat.core.events import Event
from sqlmat.test import SchemaRegistry, Table


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def adapter(conn: redshift_connector.Connection, events: list[Event]) -> RedshiftAdapter:
    return RedshiftAdapter(conn, event_handler=events.append)


@pytest.fixture
def executor(adapter: RedshiftAdapter, events: list[Event]) -> Executor:
    return Executor(adapter, event_handler=events.append)


@pytest.fixture
def unload_s3_uri(redshift_env: RedshiftEnv, test_function_id: str) -> str:
    return normalize_path(f"{redshift_env.unload_s3_uri}/redshift_unload_{test_function_id}/")


def test_unload_events(
    executor: Executor, registry: SchemaRegistry, src_table: Table, events: list[Event], unload_s3_uri: str, redshift_env: RedshiftEnv
) -> None:
    src_table.insert([(1, "2024-01-01", 5)])

    executor.run(
        Unload(
            sql="select user_id, event_date, event_count from {{ source_table }}",
            destination=unload_s3_uri,
            format="parquet",
            options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'"],
        ),
        template_context={"source_table": src_table.qualified_name},
    )

    assert events == [
        unload_started(unload_s3_uri, "parquet"),
        sql_rendered(),
        data_unloaded(),
        unload_completed(unload_s3_uri, "parquet"),
    ]


def test_unload_error_events(executor: Executor, events: list[Event], unload_s3_uri: str, redshift_env: RedshiftEnv) -> None:
    with pytest.raises(redshift_connector.error.ProgrammingError):
        executor.run(
            Unload(
                sql="select * from nonexistent_table",
                destination=unload_s3_uri,
                format="parquet",
                options=[f"IAM_ROLE '{redshift_env.unload_iam_role}'"],
            )
        )

    assert events == [
        unload_started(unload_s3_uri, "parquet"),
        sql_rendered(),
        unload_failed(unload_s3_uri, "parquet"),
    ]
