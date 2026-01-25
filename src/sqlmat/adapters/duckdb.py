from sqlmat.adapters.base import Adapter


class DuckDBAdapter(Adapter):
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql: str) -> None:
        self.conn.execute(sql)

    def create_table_as(self, schema: str, table: str, sql: str) -> None:
        full_table_name = f"{schema}.{table}"
        create_sql = f"create table {full_table_name} as {sql}"
        self.conn.execute(create_sql)

    def drop_table(self, schema: str, table: str) -> None:
        full_table_name = f"{schema}.{table}"
        drop_sql = f"drop table if exists {full_table_name}"
        self.conn.execute(drop_sql)
