from typing import Literal


class Transformation:
    target_schema: str
    target_table: str
    sql: str
    materialization: Literal["full_refresh", "delete_insert"] = "full_refresh"
    unique_key: str | list[str] | None = None

    def get_full_table_name(self) -> str:
        return f"{self.target_schema}.{self.target_table}"
