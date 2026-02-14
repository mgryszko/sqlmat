from typing import Any

from sqlmat.core.events import (
    DataUnloaded,
    RowsDeleted,
    RowsInserted,
    RowsMerged,
    SqlExecuted,
    SqlRendered,
    TableCreated,
    TableDropped,
    TableExistenceChecked,
    TransactionBegun,
    TransactionCommitted,
    TransactionRolledBack,
    TransformationCompleted,
    TransformationFailed,
    TransformationStarted,
    UnloadCompleted,
    UnloadFailed,
    UnloadStarted,
)


class _EventMatcher:
    def __init__(self, event_type: type, **fields: Any) -> None:
        self._event_type = event_type
        self._fields = fields

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self._event_type):
            return False
        for field, value in self._fields.items():
            if getattr(other, field) != value:
                return False
        if "sql" not in self._fields and hasattr(other, "sql"):
            if other.sql == "":
                return False
        if self._event_type is TransformationFailed and "error" not in self._fields:
            if other.error is None:
                return False
        if self._event_type is UnloadFailed and "error" not in self._fields:
            if other.error is None:
                return False
        return True

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._fields.items())
        return f"{self._event_type.__name__}({fields})"


def data_unloaded() -> _EventMatcher:
    return _EventMatcher(DataUnloaded)


def rows_deleted(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(RowsDeleted, schema=schema, table=table)


def rows_inserted(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(RowsInserted, schema=schema, table=table)


def rows_merged(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(RowsMerged, schema=schema, table=table)


def sql_executed() -> _EventMatcher:
    return _EventMatcher(SqlExecuted)


def sql_rendered(schema: str | None = None, table: str | None = None) -> _EventMatcher:
    kwargs: dict[str, str] = {}
    if schema is not None:
        kwargs["target_schema"] = schema
    if table is not None:
        kwargs["target_table"] = table
    return _EventMatcher(SqlRendered, **kwargs)


def table_created(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(TableCreated, schema=schema, table=table)


def table_dropped(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(TableDropped, schema=schema, table=table)


def table_existence_checked(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(TableExistenceChecked, schema=schema, table=table)


def table_transformation_completed(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(TransformationCompleted, target_schema=schema, target_table=table)


def table_transformation_failed(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(TransformationFailed, target_schema=schema, target_table=table)


def table_transformation_started(schema: str, table: str) -> _EventMatcher:
    return _EventMatcher(TransformationStarted, target_schema=schema, target_table=table)


def transaction_begun() -> _EventMatcher:
    return _EventMatcher(TransactionBegun)


def transaction_committed() -> _EventMatcher:
    return _EventMatcher(TransactionCommitted)


def transaction_rolled_back() -> _EventMatcher:
    return _EventMatcher(TransactionRolledBack)


def unload_completed(destination: str, fmt: str) -> _EventMatcher:
    return _EventMatcher(UnloadCompleted, destination=destination, format=fmt)


def unload_failed(destination: str, fmt: str) -> _EventMatcher:
    return _EventMatcher(UnloadFailed, destination=destination, format=fmt)


def unload_started(destination: str, fmt: str) -> _EventMatcher:
    return _EventMatcher(UnloadStarted, destination=destination, format=fmt)
