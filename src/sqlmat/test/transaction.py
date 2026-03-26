from types import TracebackType


class DuckDBTx:
    """Context manager that wraps a DuckDB connection in a transaction. Commits on success, rolls back on exception."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def __enter__(self) -> DuckDBTx:
        self._conn.execute("begin transaction")
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        if exc_type is None:
            self._conn.execute("commit")
        else:
            self._conn.execute("rollback")


class PostgresTx:
    """Context manager that wraps a PostgreSQL connection in a transaction. Commits on success, rolls back on exception."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def __enter__(self) -> PostgresTx:
        self._conn.cursor().execute("begin")
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        if exc_type is None:
            self._conn.cursor().execute("commit")
        else:
            self._conn.cursor().execute("rollback")


class RedshiftTx:
    """Context manager that wraps a Redshift connection in a transaction. Commits on success, rolls back on exception."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def __enter__(self) -> RedshiftTx:
        self._conn.cursor().execute("begin transaction")
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        if exc_type is None:
            self._conn.cursor().execute("commit")
        else:
            self._conn.cursor().execute("rollback")
