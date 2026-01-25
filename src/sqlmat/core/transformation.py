class Transformation:
    target_schema: str
    target_table: str
    sql: str

    def get_full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"
