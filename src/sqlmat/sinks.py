import logging

from sqlmat.core.events import (
    CopyCompleted,
    CopyFailed,
    CopyStarted,
    DataLoaded,
    DataUnloaded,
    Event,
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


class PythonLoggingSink:
    """Event handler that routes sqlmat events to Python's logging module.

    High-level events (transformation/copy/unload started/completed/failed) are logged at INFO/ERROR.
    Low-level SQL events are logged at DEBUG. Uses the "sqlmat" logger by default.
    """

    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger("sqlmat")

    def __call__(self, event: Event) -> None:
        match event:
            case CopyCompleted(target_schema=s, target_table=t):
                self._logger.info("Completed copy for %s.%s", s, t)
            case CopyFailed(target_schema=s, target_table=t, error=e):
                self._logger.error("Failed copy for %s.%s: %s", s, t, e)
            case CopyStarted(source=src, target_schema=s, target_table=t, format=f):
                self._logger.info("Starting %s copy from %s to %s.%s", f, src, s, t)
            case DataLoaded(sql=sql):
                self._logger.debug("Data loaded: %s", sql)
            case DataUnloaded(sql=sql):
                self._logger.debug("Data unloaded: %s", sql)
            case RowsDeleted(schema=s, table=t, sql=sql):
                self._logger.debug("Delete from %s.%s: %s", s, t, sql)
            case RowsInserted(schema=s, table=t, sql=sql):
                self._logger.debug("Insert into %s.%s: %s", s, t, sql)
            case RowsMerged(schema=s, table=t, sql=sql):
                self._logger.debug("Merge into %s.%s: %s", s, t, sql)
            case SqlExecuted(sql=sql):
                self._logger.debug("SQL: %s", sql)
            case SqlRendered(sql=sql):
                self._logger.debug("Rendered SQL: %s", sql)
            case TableCreated(schema=s, table=t, sql=sql):
                self._logger.debug("Create table %s.%s: %s", s, t, sql)
            case TableDropped(schema=s, table=t, sql=sql):
                self._logger.debug("Drop table %s.%s: %s", s, t, sql)
            case TableExistenceChecked(schema=s, table=t, sql=sql):
                self._logger.debug("Table exists check %s.%s: %s", s, t, sql)
            case TransactionBegun(sql=sql) | TransactionCommitted(sql=sql) | TransactionRolledBack(sql=sql):
                self._logger.debug("Transaction: %s", sql)
            case TransformationCompleted(target_schema=s, target_table=t, materialization=m):
                self._logger.info("Completed %s transformation for %s.%s", m, s, t)
            case TransformationFailed(target_schema=s, target_table=t, error=e):
                self._logger.error("Failed transformation for %s.%s: %s", s, t, e)
            case TransformationStarted(target_schema=s, target_table=t, materialization=m):
                self._logger.info("Starting %s transformation for %s.%s", m, s, t)
            case UnloadCompleted(destination=d, format=f):
                self._logger.info("Completed %s unload to %s", f, d)
            case UnloadFailed(destination=d, format=f, error=e):
                self._logger.error("Failed %s unload to %s: %s", f, d, e)
            case UnloadStarted(destination=d, format=f):
                self._logger.info("Starting %s unload to %s", f, d)
