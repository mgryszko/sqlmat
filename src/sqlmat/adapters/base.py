from abc import ABC, abstractmethod


class Adapter(ABC):
    @abstractmethod
    def execute(self, sql: str) -> None:
        pass

    @abstractmethod
    def create_table_as(self, schema: str, table: str, sql: str) -> None:
        pass

    @abstractmethod
    def drop_table(self, schema: str, table: str) -> None:
        pass

    @abstractmethod
    def table_exists(self, schema: str, table: str) -> bool:
        pass

    @abstractmethod
    def get_columns(self, schema: str, table: str) -> list[str]:
        pass

    @abstractmethod
    def delete_with_using(self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str]) -> None:
        pass

    @abstractmethod
    def delete_with_in(self, target_schema: str, target_table: str, temp_table: str, unique_key: str) -> None:
        pass

    @abstractmethod
    def insert_from_select(self, target_schema: str, target_table: str, columns: list[str], temp_table: str) -> None:
        pass
