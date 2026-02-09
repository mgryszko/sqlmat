from sqlmat.adapters.base import TARGET_TABLE_ALIAS, Adapter


class RedshiftAdapter(Adapter):
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql: str) -> None:
        self._execute(sql)

    def table_exists(self, schema: str, table: str) -> bool:
        result = self._fetchone(
            """
            select count(*)
            from information_schema.tables
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            """,
            [schema, table],
        )
        return result[0] > 0

    def get_columns(self, schema: str, table: str) -> list[str]:
        result = self._fetchall(
            """
            select column_name
            from information_schema.columns
            where lower(table_schema) = lower(?)
              and lower(table_name) = lower(?)
            order by ordinal_position
            """,
            [schema, table],
        )
        return [row[0] for row in result]

    def create_table_as(self, schema: str, table: str, sql: str) -> None:
        full_table_name = f"{schema}.{table}"
        self._execute(f"create table {full_table_name} as {sql}")

    def drop_table(self, schema: str, table: str) -> None:
        full_table_name = f"{schema}.{table}"
        self._execute(f"drop table if exists {full_table_name}")

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
        self._execute(delete_sql)

    def insert_from_select(self, target_schema: str, target_table: str, columns: list[str], temp_table: str) -> None:
        full_target = f"{target_schema}.{target_table}"
        columns_str = ", ".join(columns)
        insert_sql = f"""
            insert into {full_target} ({columns_str})
            select {columns_str} from {temp_table}
        """
        self._execute(insert_sql)

    def merge(
        self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        full_target = f"{target_schema}.{target_table}"
        join_conditions = " and ".join([f"{temp_table}.{key} = {full_target}.{key}" for key in unique_keys])

        on_clause = join_conditions
        if predicates:
            predicate_conditions = " and ".join(self._resolve_predicates(predicates, full_target))
            on_clause = f"{join_conditions} and {predicate_conditions}"

        columns = self.get_columns(target_schema, target_table)
        non_key_columns = [c for c in columns if c not in unique_keys]

        update_set = ", ".join([f"{c} = {temp_table}.{c}" for c in non_key_columns])
        insert_columns = ", ".join(columns)
        insert_values = ", ".join([f"{temp_table}.{c}" for c in columns])

        merge_sql = f"""
            merge into {full_target}
            using {temp_table}
            on {on_clause}
            when matched then update set {update_set}
            when not matched then insert ({insert_columns}) values ({insert_values})
        """
        self._execute(merge_sql)

    @staticmethod
    def _resolve_predicates(predicates: list[str], full_target: str) -> list[str]:
        return [p.replace(f"{TARGET_TABLE_ALIAS}.", f"{full_target}.") for p in predicates]

    def begin_transaction(self) -> None:
        self._execute("begin transaction")

    def commit(self) -> None:
        self._execute("commit")

    def rollback(self) -> None:
        self._execute("rollback")

    def _execute(self, sql: str, params: list | None = None) -> None:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)

    def _fetchone(self, sql: str, params: list | None = None):
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()

    def _fetchall(self, sql: str, params: list | None = None):
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

