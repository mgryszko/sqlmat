from typing import Literal


class FullRefreshTableTransformation:
    target_schema: str
    target_table: str
    sql: str

    def get_full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


class IncrementalTableTransformation:
    target_schema: str
    target_table: str
    sql: str
    strategy: Literal["delete_insert", "merge"]
    unique_key: str | list[str] | None = None
    incremental_predicates: str | list[str] | None = None

    def get_full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


class Unload:
    sql: str
    destination: str
    format: Literal["parquet", "csv", "json"]
    options: list[str] | None = None


class Copy:
    source: str
    target_schema: str
    target_table: str
    format: Literal["parquet", "csv", "json"]
    columns: list[tuple[str, str]] | None = None
    options: list[str] | None = None
