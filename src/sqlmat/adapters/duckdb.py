from sqlmat.adapters.base import SOURCE_TABLE_ALIAS, TARGET_TABLE_ALIAS, Adapter
from sqlmat.core.events import (
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
    _noop_handler,
)


class DuckDBAdapter(Adapter):
    def __init__(self, conn, event_handler: EventHandler = _noop_handler):
        super().__init__(event_handler)
        self.conn = conn

    def execute(self, sql: str) -> None:
        self._emit(SqlExecuted(sql=sql))
        self.conn.execute(sql)

    def table_exists(self, schema: str, table: str) -> bool:
        sql = """
            select count(*)
            from system.information_schema.tables
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            """
        self._emit(TableExistenceChecked(schema=schema, table=table, sql=sql))
        result = self.conn.execute(sql, [schema, table]).fetchone()
        return result[0] > 0

    def get_columns(self, schema: str, table: str) -> list[str]:
        result = self.conn.execute(
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
        self.conn.execute(create_sql)

    def drop_table(self, schema: str, table: str) -> None:
        full_table_name = f"{schema}.{table}"
        drop_sql = f"drop table if exists {full_table_name}"
        self._emit(TableDropped(schema=schema, table=table, sql=drop_sql))
        self.conn.execute(drop_sql)

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
        self.conn.execute(delete_sql)

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
        self.conn.execute(delete_sql)

    def insert_from_select(self, target_schema: str, target_table: str, columns: list[str], temp_table: str) -> None:
        full_target = f"{target_schema}.{target_table}"
        columns_str = ", ".join(columns)
        insert_sql = f"""
            insert into {full_target} ({columns_str})
            select {columns_str} from {temp_table}
        """
        self._emit(RowsInserted(schema=target_schema, table=target_table, sql=insert_sql))
        self.conn.execute(insert_sql)

    def merge(
        self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"
        join_conditions = " and ".join([f"{SOURCE_TABLE_ALIAS}.{key} = {TARGET_TABLE_ALIAS}.{key}" for key in unique_keys])

        on_clause = join_conditions
        if predicates:
            predicate_conditions = " and ".join(predicates)
            on_clause = f"{join_conditions} and {predicate_conditions}"

        merge_sql = f"""
            merge into {full_target} as {TARGET_TABLE_ALIAS}
            using {temp_table} as {SOURCE_TABLE_ALIAS}
            on {on_clause}
            when matched then update set *
            when not matched then insert *
        """
        self._emit(RowsMerged(schema=target_schema, table=target_table, sql=merge_sql))
        self.conn.execute(merge_sql)

    def begin_transaction(self) -> None:
        sql = "begin transaction"
        self._emit(TransactionBegun(sql=sql))
        self.conn.execute(sql)

    def commit(self) -> None:
        sql = "commit"
        self._emit(TransactionCommitted(sql=sql))
        self.conn.execute(sql)

    def rollback(self) -> None:
        sql = "rollback"
        self._emit(TransactionRolledBack(sql=sql))
        self.conn.execute(sql)
