from uuid import uuid4


class SchemaRegistry:
    def __init__(self, conn):
        self._conn = conn
        self._created_tables: list[tuple[str, str]] = []
        self._created_schemas: list[str] = []

    def create_schema(self, prefix: str | None = None) -> str:
        suffix = uuid4().hex[:8]
        name = f"{prefix}_{suffix}" if prefix else f"s{suffix}"
        self._conn.cursor().execute(f"create schema {name}")
        self._created_schemas.append(name)
        return name

    def register(self, schema: str, name: str) -> None:
        self._created_tables.append((schema, name))

    def teardown(self) -> None:
        for schema, name in reversed(self._created_tables):
            self._conn.cursor().execute(f"drop table if exists {schema}.{name}")
        for schema in reversed(self._created_schemas):
            self._conn.cursor().execute(f"drop schema if exists {schema} cascade")
