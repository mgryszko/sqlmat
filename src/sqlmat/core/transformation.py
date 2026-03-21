from typing import Literal


class FullRefreshTableTransformation:
    """Base class for full-refresh SQL transformations. Subclass and set target_schema, target_table, and sql.

    The sql attribute is a Jinja2 template. The implicit ``{{ target_table }}`` parameter resolves
    to ``<target_schema>.<target_table>``. Additional parameters can be passed via template_context
    when calling Executor.run().
    """

    target_schema: str
    target_table: str
    sql: str

    def get_full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


class IncrementalTableTransformation:
    """Base class for incremental SQL transformations with delete_insert or merge strategy.

    Subclass and set target_schema, target_table, sql, strategy, and unique_key.
    The sql attribute is a Jinja2 template with the same implicit parameters as
    FullRefreshTableTransformation. If the target table does not exist, it is created
    from the query result. On subsequent runs, rows are merged according to the chosen strategy.
    """

    target_schema: str
    target_table: str
    sql: str
    strategy: Literal["delete_insert", "merge"]
    unique_key: str | list[str] | None = None
    incremental_predicates: str | list[str] | None = None

    def get_full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


class Unload:
    """Exports query results to a file or external storage.

    The sql attribute is a Jinja2 template rendered with template_context passed to Executor.run().
    The format and options are adapter-specific.
    """

    sql: str
    destination: str
    format: Literal["parquet", "csv", "json"]
    options: list[str] | None = None


class Copy:
    """Loads data from a file or external storage into a table.

    The target table is dropped and recreated on every run. The columns attribute is required
    for Athena, Redshift, and PostgreSQL adapters. The format and options are adapter-specific.
    """

    source: str
    target_schema: str
    target_table: str
    format: Literal["parquet", "csv", "json"]
    columns: list[tuple[str, str]] | None = None
    options: list[str] | None = None
