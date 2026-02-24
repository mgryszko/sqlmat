from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from sqlmat.paths import normalize_path
from sqlmat.test.schema_registry import SchemaRegistry

type ColumnSpec = list[tuple[str, str]]
type Row = tuple | dict[str, object]
type Execute = Callable[..., Any]


class Table(ABC):
    def __init__(self, conn, schema: str, name: str, columns: ColumnSpec):
        self._conn = conn
        self._schema = schema
        self._name = name
        self._columns = columns

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
    def _execute(self) -> Execute:
        pass

    def delete(self, where: str | None = None) -> None:
        sql = f"delete from {self.qualified_name}"
        if where:
            sql += f" where {where}"
        self._execute()(sql)

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
        cols = columns if columns else [name for name, _ in self._columns]
        cursor = self._execute()(f"select {', '.join(cols)} from {self.qualified_name}")
        return [dict(zip(cols, row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def _sort_key(order_by: list[str] | None = None):
        if order_by:
            return lambda row: tuple(row[col] for col in order_by)
        return lambda row: tuple(row.values())


class DuckDBTable(Table):
    def create(self, registry: SchemaRegistry) -> DuckDBTable:
        _create_native_table(execute=self._execute(), table_qualified_name=self.qualified_name, columns=self._columns, registry=registry)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_positional_params(
            execute=self._execute(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
            placeholder="?",
        )

    def _execute(self) -> Execute:
        return self._conn.execute


class RedshiftTable(Table):
    def create(self, registry: SchemaRegistry) -> RedshiftTable:
        _create_native_table(execute=self._execute(), table_qualified_name=self.qualified_name, columns=self._columns, registry=registry)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_positional_params(
            execute=self._execute(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
            placeholder="%s",
        )

    def _execute(self) -> Execute:
        return self._conn.cursor().execute


class PostgresTable(Table):
    def create(self, registry: SchemaRegistry) -> PostgresTable:
        _create_native_table(execute=self._execute(), table_qualified_name=self.qualified_name, columns=self._columns, registry=registry)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_positional_params(
            execute=self._execute(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
            placeholder="%s",
        )

    def _execute(self) -> Execute:
        return self._conn.cursor().execute


class AthenaTable(Table):
    def __init__(self, conn, schema: str, name: str, columns: ColumnSpec, s3_table_base_uri: str):
        super().__init__(conn, schema, name, columns)
        self._s3_table_base_uri = s3_table_base_uri

    def create(self, registry: SchemaRegistry) -> AthenaTable:
        _create_iceberg_table(
            execute=self._execute(),
            table_qualified_name=self.qualified_name,
            columns=self._columns,
            location=normalize_path(f"{self._s3_table_base_uri}/{self._name}/"),
            registry=registry,
        )
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        _insert_named_params(
            execute=self._execute(),
            qualified_table_name=self.qualified_name,
            rows=rows,
            defaults=defaults,
            columns=self._columns,
        )

    def _execute(self) -> Execute:
        return self._conn.cursor().execute


def _create_native_table(execute: Execute, table_qualified_name: str, columns: ColumnSpec, registry: SchemaRegistry) -> None:
    cols = ", ".join(f"{name} {typ}" for name, typ in columns)
    execute(f"create table {table_qualified_name} ({cols})")
    registry.register(table_qualified_name)


def _create_iceberg_table(
    execute: Execute, table_qualified_name: str, columns: ColumnSpec, location: str, registry: SchemaRegistry
) -> None:
    cols = ", ".join(f"{name} {typ}" for name, typ in columns)
    sql = f"create table {table_qualified_name} ({cols}) location '{location}' tblproperties ('table_type' = 'ICEBERG')"
    execute(sql)
    registry.register(table_qualified_name)


def _insert_positional_params(
    execute: Execute,
    qualified_table_name: str,
    rows: list[tuple | dict[str, object]],
    defaults: dict[str, object] | None,
    columns: ColumnSpec,
    placeholder: str,
) -> None:
    for row in rows:
        if isinstance(row, tuple):
            placeholders = ", ".join(placeholder for _ in row)
            sql = f"insert into {qualified_table_name} values ({placeholders})"
            execute(sql, list(row))
        else:
            merged = {**(defaults or {}), **row}
            column_names = [name for name, _ in columns]
            col_list = ", ".join(column_names)
            placeholders = ", ".join(placeholder for _ in column_names)
            values = [merged[c] for c in column_names]
            sql = f"insert into {qualified_table_name} ({col_list}) values ({placeholders})"
            execute(sql, values)


def _insert_named_params(
    execute: Execute, qualified_table_name: str, rows: list[Row], defaults: dict[str, object] | None, columns: ColumnSpec
) -> None:
    column_names = [name for name, _ in columns]
    placeholders = ", ".join(f"%({name})s" for name in column_names)
    sql = f"insert into {qualified_table_name} ({', '.join(column_names)}) values ({placeholders})"
    for row in rows:
        if isinstance(row, tuple):
            values = dict(zip(column_names, row, strict=True))
        else:
            values = {**(defaults or {}), **row}
        execute(sql, values)
