from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class TransformationStarted:
    target_schema: str
    target_table: str
    materialization: str


@dataclass(frozen=True)
class SqlRendered:
    sql: str
    target_schema: str | None = None
    target_table: str | None = None


@dataclass(frozen=True)
class TransformationCompleted:
    target_schema: str
    target_table: str
    materialization: str


@dataclass(frozen=True)
class TransformationFailed:
    target_schema: str
    target_table: str
    materialization: str
    error: Exception


@dataclass(frozen=True)
class UnloadStarted:
    destination: str
    format: str


@dataclass(frozen=True)
class UnloadCompleted:
    destination: str
    format: str


@dataclass(frozen=True)
class UnloadFailed:
    destination: str
    format: str
    error: Exception


@dataclass(frozen=True)
class DataUnloaded:
    sql: str


@dataclass(frozen=True)
class TransactionBegun:
    sql: str


@dataclass(frozen=True)
class TransactionCommitted:
    sql: str


@dataclass(frozen=True)
class TransactionRolledBack:
    sql: str


@dataclass(frozen=True)
class TableDropped:
    schema: str
    table: str
    sql: str


@dataclass(frozen=True)
class TableCreated:
    schema: str
    table: str
    sql: str


@dataclass(frozen=True)
class TableExistenceChecked:
    schema: str
    table: str
    sql: str


@dataclass(frozen=True)
class RowsDeleted:
    schema: str
    table: str
    sql: str


@dataclass(frozen=True)
class RowsInserted:
    schema: str
    table: str
    sql: str


@dataclass(frozen=True)
class RowsMerged:
    schema: str
    table: str
    sql: str


@dataclass(frozen=True)
class SqlExecuted:
    sql: str


type Event = (
    TransformationStarted
    | SqlRendered
    | TransformationCompleted
    | TransformationFailed
    | UnloadStarted
    | UnloadCompleted
    | UnloadFailed
    | DataUnloaded
    | TransactionBegun
    | TransactionCommitted
    | TransactionRolledBack
    | TableDropped
    | TableCreated
    | TableExistenceChecked
    | RowsDeleted
    | RowsInserted
    | RowsMerged
    | SqlExecuted
)
type EventHandler = Callable[[Event], None]


def noop_handler(_event: Event) -> None:
    pass
