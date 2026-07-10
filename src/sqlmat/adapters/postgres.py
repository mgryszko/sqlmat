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


class PostgresAdapter(Adapter):
    """Adapter for PostgreSQL. Accepts a DB-API 2.0 connection (psycopg2 or psycopg 3)."""

    def __init__(self, conn, event_handler: EventHandler = noop_handler):
        super().__init__(event_handler)
        self._conn = conn

    def execute(self, sql: str) -> None:
        self._emit(SqlExecuted(sql=sql))
        self._execute(sql)

    def table_exists(self, schema: str, table: str) -> bool:
        sql = """
            select count(*)
            from information_schema.tables
            where lower(table_schema) = lower(%s)
              and lower(table_name) = lower(%s)
            """
        self._emit(TableExistenceChecked(schema=schema, table=table, sql=sql))
        result = self._fetchone(sql, [schema, table])
        return result[0] > 0

    def get_columns(self, schema: str, table: str) -> list[str]:
        result = self._fetchall(
            """
            select column_name
            from information_schema.columns
            where lower(table_schema) = lower(%s)
              and lower(table_name) = lower(%s)
            order by ordinal_position
            """,
            [schema, table],
        )
        return [row[0] for row in result]

    def create_table_as(self, schema: str, table: str, sql: str) -> None:
        full_table_name = f"{schema}.{table}"
        create_sql = f"create table {full_table_name} as {sql}"
        self._emit(TableCreated(schema=schema, table=table, sql=create_sql))
        self._execute(create_sql)

    def drop_table(self, schema: str, table: str) -> None:
        full_table_name = f"{schema}.{table}"
        drop_sql = f"drop table if exists {full_table_name}"
        self._emit(TableDropped(schema=schema, table=table, sql=drop_sql))
        self._execute(drop_sql)

    def rename_table(self, schema: str, old_name: str, new_name: str) -> None:
        rename_sql = f"alter table {schema}.{old_name} rename to {new_name}"
        self._emit(SqlExecuted(sql=rename_sql))
        self._execute(rename_sql)

    def delete_with_using(
        self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"
        join_conditions = " and ".join([f"{temp_table}.{key} = {full_target}.{key}" for key in unique_keys])

        where_clause = join_conditions
        if predicates:
            predicate_conditions = " and ".join(self._resolve_predicates(predicates, full_target))
            where_clause = f"{join_conditions} and {predicate_conditions}"

        delete_sql = f"""
            delete from {full_target}
            using {temp_table}
            where {where_clause}
        """
        self._emit(RowsDeleted(schema=target_schema, table=target_table, sql=delete_sql))
        self._execute(delete_sql)

    def delete_with_in(
        self, target_schema: str, target_table: str, temp_table: str, unique_key: str, predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"

        where_clause = f"({full_target}.{unique_key}) in (select ({unique_key}) from {temp_table})"
        if predicates:
            predicate_conditions = " and ".join(self._resolve_predicates(predicates, full_target))
            where_clause = f"{where_clause} and {predicate_conditions}"

        delete_sql = f"""
            delete from {full_target}
            where {where_clause}
        """
        self._emit(RowsDeleted(schema=target_schema, table=target_table, sql=delete_sql))
        self._execute(delete_sql)

    def insert_from_select(self, target_schema: str, target_table: str, columns: list[str], temp_table: str) -> None:
        full_target = f"{target_schema}.{target_table}"
        columns_str = ", ".join(columns)
        insert_sql = f"""
            insert into {full_target} ({columns_str})
            select {columns_str} from {temp_table}
        """
        self._emit(RowsInserted(schema=target_schema, table=target_table, sql=insert_sql))
        self._execute(insert_sql)

    def insert_into(self, target_schema: str, target_table: str, source_sql: str) -> None:
        full_target = f"{target_schema}.{target_table}"
        insert_sql = f"insert into {full_target} {source_sql}"
        self._emit(RowsInserted(schema=target_schema, table=target_table, sql=insert_sql))
        self._execute(insert_sql)

    def merge(
        self, target_schema: str, target_table: str, source_sql: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"
        join_conditions = " and ".join([f"{SOURCE_TABLE_ALIAS}.{key} = {full_target}.{key}" for key in unique_keys])

        on_clause = join_conditions
        if predicates:
            predicate_conditions = " and ".join(self._resolve_predicates(predicates, full_target))
            on_clause = f"{join_conditions} and {predicate_conditions}"

        columns = self.get_columns(target_schema, target_table)
        non_key_columns = [c for c in columns if c not in unique_keys]

        update_set = ", ".join([f"{c} = {SOURCE_TABLE_ALIAS}.{c}" for c in non_key_columns])
        insert_columns = ", ".join(columns)
        insert_values = ", ".join([f"{SOURCE_TABLE_ALIAS}.{c}" for c in columns])

        merge_sql = f"""
            merge into {full_target}
            using ({source_sql}) as {SOURCE_TABLE_ALIAS}
            on {on_clause}
            when matched then update set {update_set}
            when not matched then insert ({insert_columns}) values ({insert_values})
        """
        self._emit(RowsMerged(schema=target_schema, table=target_table, sql=merge_sql))
        self._execute(merge_sql)

    @staticmethod
    def _resolve_predicates(predicates: list[str], full_target: str) -> list[str]:
        return [p.replace(f"{TARGET_TABLE_ALIAS}.", f"{full_target}.") for p in predicates]

    def begin_transaction(self) -> None:
        sql = "begin"
        self._emit(TransactionBegun(sql=sql))
        self._execute(sql)

    def commit(self) -> None:
        sql = "commit"
        self._emit(TransactionCommitted(sql=sql))
        self._execute(sql)

    def rollback(self) -> None:
        sql = "rollback"
        self._emit(TransactionRolledBack(sql=sql))
        self._execute(sql)

    def copy_from(
        self,
        source: str,
        schema: str,
        table: str,
        fmt: str,
        columns: list[tuple[str, str]] | None = None,
        options: list[str] | None = None,
    ) -> None:
        if fmt != "csv":
            raise ValueError(f"PostgreSQL adapter only supports CSV format for copy, got: {fmt}")
        if columns is None:
            raise ValueError("PostgreSQL adapter requires columns for copy_from")

        full_table_name = f"{schema}.{table}"
        cols_sql = ", ".join(f"{name} {typ}" for name, typ in columns)
        create_sql = f"create table {full_table_name} ({cols_sql})"
        self._emit(TableCreated(schema=schema, table=table, sql=create_sql))
        self._execute(create_sql)

        with_clause = ", ".join(["format csv"] + (options or []))
        copy_sql = f"copy {full_table_name} from stdin with ({with_clause})"
        with self._conn.cursor() as cur:
            self._copy_from_stdin(cur, copy_sql, source)
        self._emit(DataLoaded(sql=copy_sql))

    def copy_to(self, sql: str, destination: str, fmt: str, options: list[str] | None = None) -> None:
        if fmt != "csv":
            raise ValueError(f"PostgreSQL adapter only supports CSV format for unload, got: {fmt}")

        with_clause = ", ".join(["format csv"] + (options or []))
        copy_sql = f"copy ({sql}) to stdout with ({with_clause})"
        with self._conn.cursor() as cur:
            self._copy_to_stdout(cur, copy_sql, destination)
        self._emit(DataUnloaded(sql=copy_sql))

    # psycopg2 uses copy_expert(sql, file); psycopg3 uses cursor.copy(sql) context manager.
    # Both branches are unified here so the adapter works with either driver.
    @staticmethod
    def _copy_from_stdin(cur, copy_sql: str, source: str) -> None:
        with open(source, "rb") as f:
            if hasattr(cur, "copy_expert"):
                cur.copy_expert(copy_sql, f)
            else:
                with cur.copy(copy_sql) as copy:
                    while data := f.read(8192):
                        copy.write(data)

    # For psycopg3 the file is opened inside the cur.copy() context so that SQL errors
    # (raised when entering the context) propagate before the destination file is created.
    @staticmethod
    def _copy_to_stdout(cur, copy_sql: str, destination: str) -> None:
        if hasattr(cur, "copy_expert"):
            with open(destination, "wb") as f:
                cur.copy_expert(copy_sql, f)
        else:
            with cur.copy(copy_sql) as copy:
                with open(destination, "wb") as f:
                    for data in copy:
                        f.write(data)

    def _execute(self, sql: str, params: list | None = None) -> None:
        cursor = self._conn.cursor()
        cursor.execute(sql, params)

    def _fetchone(self, sql: str, params: list | None = None):
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()

    def _fetchall(self, sql: str, params: list | None = None):
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()
