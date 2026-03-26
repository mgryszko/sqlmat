from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Failure:
    error: Exception


@dataclass(frozen=True)
class SqlEvent:
    sql: str


@dataclass(frozen=True)
class CopyCompleted:
    source: str
    target_schema: str
    target_table: str
    format: str


@dataclass(frozen=True)
class CopyFailed(Failure):
    source: str
    target_schema: str
    target_table: str
    format: str


@dataclass(frozen=True)
class CopyStarted:
    source: str
    target_schema: str
    target_table: str
    format: str


@dataclass(frozen=True)
class DataLoaded(SqlEvent):
    pass


@dataclass(frozen=True)
class DataUnloaded(SqlEvent):
    pass


@dataclass(frozen=True)
class RowsDeleted(SqlEvent):
    schema: str
    table: str


@dataclass(frozen=True)
class RowsInserted(SqlEvent):
    schema: str
    table: str


@dataclass(frozen=True)
class RowsMerged(SqlEvent):
    schema: str
    table: str


@dataclass(frozen=True)
class SqlExecuted(SqlEvent):
    pass


@dataclass(frozen=True)
class SqlRendered(SqlEvent):
    target_schema: str | None = None
    target_table: str | None = None


@dataclass(frozen=True)
class TableCreated(SqlEvent):
    schema: str
    table: str


@dataclass(frozen=True)
class TableDropped(SqlEvent):
    schema: str
    table: str


@dataclass(frozen=True)
class TableExistenceChecked(SqlEvent):
    schema: str
    table: str


@dataclass(frozen=True)
class TransactionBegun(SqlEvent):
    pass


@dataclass(frozen=True)
class TransactionCommitted(SqlEvent):
    pass


@dataclass(frozen=True)
class TransactionRolledBack(SqlEvent):
    pass


@dataclass(frozen=True)
class TransformationCompleted:
    target_schema: str
    target_table: str
    materialization: str


@dataclass(frozen=True)
class TransformationFailed(Failure):
    target_schema: str
    target_table: str
    materialization: str


@dataclass(frozen=True)
class TransformationStarted:
    target_schema: str
    target_table: str
    materialization: str


@dataclass(frozen=True)
class UnloadCompleted:
    destination: str
    format: str


@dataclass(frozen=True)
class UnloadFailed(Failure):
    destination: str
    format: str


@dataclass(frozen=True)
class UnloadStarted:
    destination: str
    format: str


type Event = (
    CopyCompleted
    | CopyFailed
    | CopyStarted
    | DataLoaded
    | DataUnloaded
    | RowsDeleted
    | RowsInserted
    | RowsMerged
    | SqlExecuted
    | SqlRendered
    | TableCreated
    | TableDropped
    | TableExistenceChecked
    | TransactionBegun
    | TransactionCommitted
    | TransactionRolledBack
    | TransformationCompleted
    | TransformationFailed
    | TransformationStarted
    | UnloadCompleted
    | UnloadFailed
    | UnloadStarted
)
type EventHandler = Callable[[Event], None]


def noop_handler(_event: Event) -> None:
    pass
