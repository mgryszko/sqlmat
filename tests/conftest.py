import os
import uuid

import pytest
from approvaltests.reporters import PythonNativeReporter, set_default_reporter
from dotenv import load_dotenv
from env import AthenaEnv, RedshiftEnv

set_default_reporter(PythonNativeReporter())

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"Missing environment variable: {name}")
    return value


@pytest.fixture
def test_function_id() -> str:
    return str(uuid.uuid4())[:8]


@pytest.fixture(scope="session")
def redshift_env() -> RedshiftEnv:
    return RedshiftEnv(
        host=_require_env("REDSHIFT_HOST"),
        port=int(os.environ.get("REDSHIFT_PORT", "5439")),
        database=_require_env("REDSHIFT_DATABASE"),
        user=_require_env("REDSHIFT_USER"),
        password=_require_env("REDSHIFT_PASSWORD"),
        schema_prefix=_require_env("REDSHIFT_SCHEMA_PREFIX"),
        unload_s3_uri=_require_env("UNLOAD_S3_URI"),
        unload_iam_role=_require_env("REDSHIFT_UNLOAD_IAM_ROLE"),
        copy_s3_uri=_require_env("COPY_S3_URI"),
        copy_iam_role=_require_env("REDSHIFT_COPY_IAM_ROLE"),
    )


@pytest.fixture(scope="session")
def athena_env() -> AthenaEnv:
    return AthenaEnv(
        s3_staging_dir=_require_env("ATHENA_S3_STAGING_DIR"),
        region=_require_env("ATHENA_REGION"),
        work_group=_require_env("ATHENA_WORK_GROUP"),
        s3_table_base_uri=_require_env("ATHENA_S3_TABLE_BASE_URI"),
        schema_prefix=_require_env("ATHENA_SCHEMA_PREFIX"),
        copy_s3_uri=_require_env("COPY_S3_URI"),
        unload_s3_uri=_require_env("UNLOAD_S3_URI"),
    )
