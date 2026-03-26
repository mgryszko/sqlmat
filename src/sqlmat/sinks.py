import logging

from sqlmat.core.events import (
    CopyCompleted,
    CopyFailed,
    CopyStarted,
    DataLoaded,
    DataUnloaded,
    Event,
    Failure,
    RowsDeleted,
    RowsInserted,
    RowsMerged,
    SqlEvent,
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


class _LazyMessage:
    def __init__(self, fmt: str, *args: object) -> None:
        self._fmt = fmt
        self._args = args

    def __str__(self) -> str:
        return self._fmt % self._args


def event_message(event: Event) -> _LazyMessage:
    """Return a lazy string describing the event. The message is only formatted when str() is called.

    Can be used to build custom logging sinks by combining with your own log-level routing or output target.
    """
    match event:
        case CopyCompleted(target_schema=s, target_table=t):
            return _LazyMessage("Completed copy for %s.%s", s, t)
        case CopyFailed(target_schema=s, target_table=t, error=e):
            return _LazyMessage("Failed copy for %s.%s: %s", s, t, e)
        case CopyStarted(source=src, target_schema=s, target_table=t, format=f):
            return _LazyMessage("Starting %s copy from %s to %s.%s", f, src, s, t)
        case DataLoaded(sql=sql):
            return _LazyMessage("Data loaded: %s", sql)
        case DataUnloaded(sql=sql):
            return _LazyMessage("Data unloaded: %s", sql)
        case RowsDeleted(schema=s, table=t, sql=sql):
            return _LazyMessage("Delete from %s.%s: %s", s, t, sql)
        case RowsInserted(schema=s, table=t, sql=sql):
            return _LazyMessage("Insert into %s.%s: %s", s, t, sql)
        case RowsMerged(schema=s, table=t, sql=sql):
            return _LazyMessage("Merge into %s.%s: %s", s, t, sql)
        case SqlExecuted(sql=sql):
            return _LazyMessage("SQL: %s", sql)
        case SqlRendered(sql=sql):
            return _LazyMessage("Rendered SQL: %s", sql)
        case TableCreated(schema=s, table=t, sql=sql):
            return _LazyMessage("Create table %s.%s: %s", s, t, sql)
        case TableDropped(schema=s, table=t, sql=sql):
            return _LazyMessage("Drop table %s.%s: %s", s, t, sql)
        case TableExistenceChecked(schema=s, table=t, sql=sql):
            return _LazyMessage("Table exists check %s.%s: %s", s, t, sql)
        case TransactionBegun(sql=sql) | TransactionCommitted(sql=sql) | TransactionRolledBack(sql=sql):
            return _LazyMessage("Transaction: %s", sql)
        case TransformationCompleted(target_schema=s, target_table=t, materialization=m):
            return _LazyMessage("Completed %s transformation for %s.%s", m, s, t)
        case TransformationFailed(target_schema=s, target_table=t, error=e):
            return _LazyMessage("Failed transformation for %s.%s: %s", s, t, e)
        case TransformationStarted(target_schema=s, target_table=t, materialization=m):
            return _LazyMessage("Starting %s transformation for %s.%s", m, s, t)
        case UnloadCompleted(destination=d, format=f):
            return _LazyMessage("Completed %s unload to %s", f, d)
        case UnloadFailed(destination=d, format=f, error=e):
            return _LazyMessage("Failed %s unload to %s: %s", f, d, e)
        case UnloadStarted(destination=d, format=f):
            return _LazyMessage("Starting %s unload to %s", f, d)


class PythonLoggingSink:
    """Event handler that routes sqlmat events to Python's logging module.

    High-level events (transformation/copy/unload started/completed/failed) are logged at INFO/ERROR.
    Low-level SQL events are logged at DEBUG. Uses the "sqlmat" logger by default.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("sqlmat")

    def __call__(self, event: Event) -> None:
        msg = event_message(event)
        match event:
            case Failure():
                self._logger.error(msg)
            case SqlEvent():
                self._logger.debug(msg)
            case _:
                self._logger.info(msg)
