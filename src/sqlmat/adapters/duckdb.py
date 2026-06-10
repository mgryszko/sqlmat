from sqlmat.adapters.base import SOURCE_TABLE_ALIAS, TARGET_TABLE_ALIAS, Adapter
from sqlmat.core.events import (
    DataLoaded,
    DataUnloaded,
    EventHandler,
    RowsDeleted,
    RowsInserted,
    RowsMerged,
    SqlExecuted,
    TableCreated,
    TableDropped,
    TableExistenceChecked,
    TransactionBegun,
    TransactionCommitted,
    TransactionRolledBack,
    noop_handler,
)


class DuckDBAdapter(Adapter):
    """Adapter for DuckDB. Accepts a duckdb.DuckDBPyConnection."""

    def __init__(self, conn, event_handler: EventHandler = noop_handler):
        super().__init__(event_handler)
        self._conn = conn

    def execute(self, sql: str) -> None:
        self._emit(SqlExecuted(sql=sql))
        self._conn.execute(sql)

    def table_exists(self, schema: str, table: str) -> bool:
        sql = """
            select count(*)
            from system.information_schema.tables
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            """
        self._emit(TableExistenceChecked(schema=schema, table=table, sql=sql))
        result = self._conn.execute(sql, [schema, table]).fetchone()
        return result[0] > 0

    def get_columns(self, schema: str, table: str) -> list[str]:
        result = self._conn.execute(
            """
            select column_name
            from system.information_schema.columns
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            order by ordinal_position
            """,
            [schema, table],
        ).fetchall()
        return [row[0] for row in result]

    def create_table_as(self, schema: str, table: str, sql: str) -> None:
        full_table_name = f"{schema}.{table}"
        create_sql = f"create table {full_table_name} as {sql}"
        self._emit(TableCreated(schema=schema, table=table, sql=create_sql))
        self._conn.execute(create_sql)

    def drop_table(self, schema: str, table: str) -> None:
        full_table_name = f"{schema}.{table}"
        drop_sql = f"drop table if exists {full_table_name}"
        self._emit(TableDropped(schema=schema, table=table, sql=drop_sql))
        self._conn.execute(drop_sql)

    def rename_table(self, schema: str, old_name: str, new_name: str) -> None:
        rename_sql = f"alter table {schema}.{old_name} rename to {new_name}"
        self._emit(SqlExecuted(sql=rename_sql))
        self._conn.execute(rename_sql)

    def delete_with_using(
        self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"
        join_conditions = " and ".join([f"{temp_table}.{key} = {TARGET_TABLE_ALIAS}.{key}" for key in unique_keys])

        where_clause = join_conditions
        if predicates:
            predicate_conditions = " and ".join(predicates)
            where_clause = f"{join_conditions} and {predicate_conditions}"

        delete_sql = f"""
            delete from {full_target} as {TARGET_TABLE_ALIAS}
            using {temp_table}
            where {where_clause}
        """
        self._emit(RowsDeleted(schema=target_schema, table=target_table, sql=delete_sql))
        self._conn.execute(delete_sql)

    def delete_with_in(
        self, target_schema: str, target_table: str, temp_table: str, unique_key: str, predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"

        where_clause = f"({TARGET_TABLE_ALIAS}.{unique_key}) in (select ({unique_key}) from {temp_table})"
        if predicates:
            predicate_conditions = " and ".join(predicates)
            where_clause = f"{where_clause} and {predicate_conditions}"

        delete_sql = f"""
            delete from {full_target} as {TARGET_TABLE_ALIAS}
            where {where_clause}
        """
        self._emit(RowsDeleted(schema=target_schema, table=target_table, sql=delete_sql))
        self._conn.execute(delete_sql)

    def insert_from_select(self, target_schema: str, target_table: str, columns: list[str], temp_table: str) -> None:
        full_target = f"{target_schema}.{target_table}"
        columns_str = ", ".join(columns)
        insert_sql = f"""
            insert into {full_target} ({columns_str})
            select {columns_str} from {temp_table}
        """
        self._emit(RowsInserted(schema=target_schema, table=target_table, sql=insert_sql))
        self._conn.execute(insert_sql)

    def merge(
        self, target_schema: str, target_table: str, source_sql: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"
        join_conditions = " and ".join([f"{SOURCE_TABLE_ALIAS}.{key} = {TARGET_TABLE_ALIAS}.{key}" for key in unique_keys])

        on_clause = join_conditions
        if predicates:
            predicate_conditions = " and ".join(predicates)
            on_clause = f"{join_conditions} and {predicate_conditions}"

        merge_sql = f"""
            merge into {full_target} as {TARGET_TABLE_ALIAS}
            using ({source_sql}) as {SOURCE_TABLE_ALIAS}
            on {on_clause}
            when matched then update set *
            when not matched then insert *
        """
        self._emit(RowsMerged(schema=target_schema, table=target_table, sql=merge_sql))
        self._conn.execute(merge_sql)

    def begin_transaction(self) -> None:
        sql = "begin transaction"
        self._emit(TransactionBegun(sql=sql))
        self._conn.execute(sql)

    def commit(self) -> None:
        sql = "commit"
        self._emit(TransactionCommitted(sql=sql))
        self._conn.execute(sql)

    def rollback(self) -> None:
        sql = "rollback"
        self._emit(TransactionRolledBack(sql=sql))
        self._conn.execute(sql)

    def copy_from(
        self,
        source: str,
        schema: str,
        table: str,
        fmt: str,
        columns: list[tuple[str, str]] | None = None,
        options: list[str] | None = None,
    ) -> None:
        read_fn = {"parquet": "read_parquet", "csv": "read_csv", "json": "read_json"}[fmt]
        args_str = ", ".join([f"'{source}'"] + (options or []))
        full_table_name = f"{schema}.{table}"
        sql = f"create table {full_table_name} as select * from {read_fn}({args_str})"
        self._conn.execute(sql)
        self._emit(DataLoaded(sql=sql))

    def copy_to(self, sql: str, destination: str, fmt: str, options: list[str] | None = None) -> None:
        options_str = ", ".join([f"format {fmt.upper()}"] + (options or []))
        copy_sql = f"copy ({sql}) to '{destination}' ({options_str})"

        self._conn.execute(copy_sql)
        self._emit(DataUnloaded(sql=copy_sql))
