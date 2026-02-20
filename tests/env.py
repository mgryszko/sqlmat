from dataclasses import dataclass


@dataclass(frozen=True)
class RedshiftEnv:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema_prefix: str
    unload_s3_uri: str
    unload_iam_role: str
    copy_s3_uri: str
    copy_iam_role: str


@dataclass(frozen=True)
class AthenaEnv:
    s3_staging_dir: str
    region: str
    work_group: str
    s3_table_base_uri: str
    schema_prefix: str
    copy_s3_uri: str
    unload_s3_uri: str
