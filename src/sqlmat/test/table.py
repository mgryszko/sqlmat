from __future__ import annotations

from sqlmat.test.schema_registry import SchemaRegistry

type ColumnSpec = list[tuple[str, str]]
type Row = tuple | dict[str, object]


class Table:
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

    def create(self, registry: SchemaRegistry) -> Table:
        cols = ", ".join(f"{name} {typ}" for name, typ in self._columns)
        self._conn.cursor().execute(f"create table {self.qualified_name} ({cols})")
        registry.register(self._schema, self._name)
        return self

    def insert(self, rows: list[Row], defaults: dict[str, object] | None = None) -> None:
        for row in rows:
            cursor = self._conn.cursor()
            if isinstance(row, tuple):
                placeholders = ", ".join("?" for _ in row)
                sql = f"insert into {self.qualified_name} values ({placeholders})"
                cursor.execute(sql, list(row))
            else:
                merged = {**(defaults or {}), **row}
                column_names = [name for name, _ in self._columns]
                col_list = ", ".join(column_names)
                placeholders = ", ".join("?" for _ in column_names)
                values = [merged[c] for c in column_names]
                sql = f"insert into {self.qualified_name} ({col_list}) values ({placeholders})"
                cursor.execute(sql, values)

    def delete(self, where: str | None = None) -> None:
        sql = f"delete from {self.qualified_name}"
        if where:
            sql += f" where {where}"
        self._conn.cursor().execute(sql)

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
        cursor = self._conn.cursor().execute(f"select {", ".join(cols)} from {self.qualified_name}")
        return [dict(zip(cols, row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def _sort_key(order_by: list[str] | None = None):
        if order_by:
            return lambda row: tuple(row[col] for col in order_by)
        return lambda row: tuple(row.values())
