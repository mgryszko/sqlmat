from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlmat.paths import normalize_path
from sqlmat.test.schema_registry import SchemaRegistry


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    wrapper: str | None = None

    def placeholder(self, raw: str) -> str:
        if self.wrapper:
            return self.wrapper.format(raw)
        return raw


type ColumnEntry = tuple[str, str] | tuple[str, str, str]
type ColumnSpec = list[ColumnEntry]
type Row = tuple | dict[str, object]


class Table(ABC):
    """Abstract base class for test table helpers.

    Provides create, insert, delete, assert_table_equals, and assert_table_contains.
    Use a database-specific subclass: DuckDBTable, PostgresTable, RedshiftTable, or AthenaTable.
    """

    def __init__(self, conn, schema: str, name: str, columns: ColumnSpec):
        self._conn = conn
        self._schema = schema
        self._name = name
        self._columns = [Column(*c) for c in columns]

    @property
    def schema(self) -> str:
        return self._schema

    @property
    def name(self) -> str:
        return self._name

    @property
    def qualified_name(self) -> str:
        return f"{self._schema}.{self._name}"

    @abstractmethod
    def create(self, registry: SchemaRegistry) -> Table:
        pass

    @abstractmethod
    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        pass

    @abstractmethod
    def _cursor(self):
        pass

    def delete(self, where: str | None = None) -> None:
        sql = f"delete from {self.qualified_name}"
        if where:
            sql += f" where {where}"
        self._cursor().execute(sql)

    def assert_table_equals(
        self,
        expected: list[dict[str, object]],
        order_by: list[str] | None = None,
        columns: list[str] | None = None,
    ) -> None:
        actual = self._fetch_as_dicts(columns)
        sort_key = self._sort_key(order_by)
        assert sorted(actual, key=sort_key) == sorted(expected, key=sort_key)

    def assert_table_contains(
        self,
        expected: list[dict[str, object]],
        order_by: list[str] | None = None,
        columns: list[str] | None = None,
    ) -> None:
        actual = self._fetch_as_dicts(columns)
        sort_key = self._sort_key(order_by)
        actual_sorted = sorted(actual, key=sort_key)
        for row in sorted(expected, key=sort_key):
            assert row in actual_sorted, f"Expected row not found: {row}"

    def _fetch_as_dicts(self, columns: list[str] | None = None) -> list[dict[str, object]]:
        cols = columns if columns else [c.name for c in self._columns]
        cur = self._cursor()
        cur.execute(f"select {', '.join(cols)} from {self.qualified_name}")
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    @staticmethod
    def _sort_key(order_by: list[str] | None = None):
        if order_by:
            return lambda row: tuple(row[col] for col in order_by)
        return lambda row: tuple(row.values())


class DuckDBTable(Table):
    def create(self, registry: SchemaRegistry) -> DuckDBTable:
        _create_native_table(cursor=self._cursor(), table_qualified_name=self.qualified_name, columns=self._columns, registry=registry)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_positional_params(
            cursor=self._cursor(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
            placeholder="?",
        )

    def _cursor(self):
        return self._conn


class RedshiftTable(Table):
    def create(self, registry: SchemaRegistry) -> RedshiftTable:
        _create_native_table(cursor=self._cursor(), table_qualified_name=self.qualified_name, columns=self._columns, registry=registry)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_positional_params(
            cursor=self._cursor(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
            placeholder="%s",
        )

    def _cursor(self):
        return self._conn.cursor()


class PostgresTable(Table):
    def create(self, registry: SchemaRegistry) -> PostgresTable:
        _create_native_table(cursor=self._cursor(), table_qualified_name=self.qualified_name, columns=self._columns, registry=registry)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_positional_params(
            cursor=self._cursor(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
            placeholder="%s",
        )

    def _cursor(self):
        return self._conn.cursor()


class AthenaTable(Table):
    def __init__(self, conn, schema: str, name: str, columns: ColumnSpec, s3_table_base_uri: str):
        super().__init__(conn, schema, name, columns)
        self._s3_table_base_uri = s3_table_base_uri

    def create(self, registry: SchemaRegistry) -> AthenaTable:
        _create_iceberg_table(
            cursor=self._cursor(),
            table_qualified_name=self.qualified_name,
            columns=self._columns,
            location=normalize_path(f"{self._s3_table_base_uri}/{self._name}/"),
            registry=registry,
        )
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_named_params(
            cursor=self._cursor(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
        )

    def _cursor(self):
        return self._conn.cursor()


def _create_native_table(cursor, table_qualified_name: str, columns: list[Column], registry: SchemaRegistry) -> None:
    cols = ", ".join(f"{c.name} {c.type}" for c in columns)
    cursor.execute(f"create table {table_qualified_name} ({cols})")
    registry.register(table_qualified_name)


def _create_iceberg_table(cursor, table_qualified_name: str, columns: list[Column], location: str, registry: SchemaRegistry) -> None:
    cols = ", ".join(f"{c.name} {c.type}" for c in columns)
    sql = f"create table {table_qualified_name} ({cols}) location '{location}' tblproperties ('table_type' = 'ICEBERG')"
    cursor.execute(sql)
    registry.register(table_qualified_name)


def _insert_positional_params(
    cursor,
    qualified_table_name: str,
    rows: list[tuple | dict[str, object]],
    defaults: dict[str, object] | None,
    columns: list[Column],
    placeholder: str,
) -> None:
    for row in rows:
        if isinstance(row, tuple):
            placeholders = ", ".join(c.placeholder(placeholder) for c in columns)
            sql = f"insert into {qualified_table_name} values ({placeholders})"
            cursor.execute(sql, list(row))
        else:
            merged = {**(defaults or {}), **row}
            column_names = [c.name for c in columns]
            col_list = ", ".join(column_names)
            placeholders = ", ".join(c.placeholder(placeholder) for c in columns)
            values = [merged[n] for n in column_names]
            sql = f"insert into {qualified_table_name} ({col_list}) values ({placeholders})"
            cursor.execute(sql, values)


def _insert_named_params(
    cursor, qualified_table_name: str, rows: list[Row], defaults: dict[str, object] | None, columns: list[Column]
) -> None:
    column_names = [c.name for c in columns]
    placeholders = ", ".join(c.placeholder(f"%({c.name})s") for c in columns)
    sql = f"insert into {qualified_table_name} ({', '.join(column_names)}) values ({placeholders})"
    for row in rows:
        if isinstance(row, tuple):
            values = dict(zip(column_names, row, strict=True))
        else:
            values = {**(defaults or {}), **row}
        cursor.execute(sql, values)
