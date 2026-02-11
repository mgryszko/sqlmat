from sqlmat.core.events import (
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
)


class _EventMatcher:
    def __init__(self, event_type, **fields):
        self._event_type = event_type
        self._fields = fields

    def __eq__(self, other):
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
        return True

    def __repr__(self):
        fields = ", ".join(f"{k}={v!r}" for k, v in self._fields.items())
        return f"{self._event_type.__name__}({fields})"


def transformation_started(schema, table):
    return _EventMatcher(TransformationStarted, target_schema=schema, target_table=table)


def sql_rendered(schema, table):
    return _EventMatcher(SqlRendered, target_schema=schema, target_table=table)


def transformation_completed(schema, table):
    return _EventMatcher(TransformationCompleted, target_schema=schema, target_table=table)


def transformation_failed(schema, table):
    return _EventMatcher(TransformationFailed, target_schema=schema, target_table=table)


def transaction_begun():
    return _EventMatcher(TransactionBegun)


def transaction_committed():
    return _EventMatcher(TransactionCommitted)


def transaction_rolled_back():
    return _EventMatcher(TransactionRolledBack)


def table_dropped(schema, table):
    return _EventMatcher(TableDropped, schema=schema, table=table)


def table_created(schema, table):
    return _EventMatcher(TableCreated, schema=schema, table=table)


def table_existence_checked(schema, table):
    return _EventMatcher(TableExistenceChecked, schema=schema, table=table)


def rows_deleted(schema, table):
    return _EventMatcher(RowsDeleted, schema=schema, table=table)


def rows_inserted(schema, table):
    return _EventMatcher(RowsInserted, schema=schema, table=table)


def rows_merged(schema, table):
    return _EventMatcher(RowsMerged, schema=schema, table=table)


def sql_executed():
    return _EventMatcher(SqlExecuted)
