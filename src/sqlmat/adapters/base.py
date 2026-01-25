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
