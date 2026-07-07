from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FullRefreshTableTransformation:
    target_schema: str
    target_table: str
    sql: str

    @property
    def full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


@dataclass(frozen=True)
class IncrementalTableTransformation:
    target_schema: str
    target_table: str
    sql: str
    strategy: Literal["delete_insert", "merge", "append"]
    unique_key: str | list[str] | None = None
    incremental_predicates: str | list[str] | None = None

    @property
    def full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


@dataclass(frozen=True)
class Unload:
    sql: str
    destination: str
    format: Literal["parquet", "csv", "json"]
    options: list[str] | None = None


@dataclass(frozen=True)
class Copy:
    source: str
    target_schema: str
    target_table: str
    format: Literal["parquet", "csv", "json"]
    columns: list[tuple[str, str]] | None = None
    options: list[str] | None = None
