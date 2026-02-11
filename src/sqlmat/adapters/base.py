from abc import ABC, abstractmethod

from sqlmat.core.events import Event, EventHandler, _noop_handler

TARGET_TABLE_ALIAS = "target"
SOURCE_TABLE_ALIAS = "source"


class Adapter(ABC):
    def __init__(self, event_handler: EventHandler = _noop_handler):
        self._event_handler = event_handler

    def _emit(self, event: Event) -> None:
        self._event_handler(event)

    @abstractmethod
    def execute(self, sql: str) -> None:
        pass

    @abstractmethod
    def table_exists(self, schema: str, table: str) -> bool:
        pass

    @abstractmethod
    def get_columns(self, schema: str, table: str) -> list[str]:
        pass

    @abstractmethod
    def create_table_as(self, schema: str, table: str, sql: str) -> None:
        pass

    @abstractmethod
    def drop_table(self, schema: str, table: str) -> None:
        pass

    @abstractmethod
    def delete_with_using(
        self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        pass

    @abstractmethod
    def delete_with_in(
        self, target_schema: str, target_table: str, temp_table: str, unique_key: str, predicates: list[str] | None = None
    ) -> None:
        pass

    @abstractmethod
    def insert_from_select(self, target_schema: str, target_table: str, columns: list[str], temp_table: str) -> None:
        pass

    @abstractmethod
    def merge(
        self, target_schema: str, target_table: str, temp_table: str, unique_keys: list[str], predicates: list[str] | None = None
    ) -> None:
        pass

    @abstractmethod
    def begin_transaction(self) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass
