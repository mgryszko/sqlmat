from uuid import uuid4


class SchemaRegistry:
    def __init__(self, conn):
        self._conn = conn
        self._created_tables: list[str] = []
        self._created_schemas: list[str] = []

    def __enter__(self) -> "SchemaRegistry":
        return self

    def __exit__(self, *_) -> None:
        self.teardown()

    def create_schema(self, prefix: str | None = None) -> str:
        suffix = uuid4().hex[:8]
        name = f"{prefix}_{suffix}" if prefix else f"s{suffix}"
        self._conn.cursor().execute(f"create schema {name}")
        self._created_schemas.append(name)
        return name

    def register(self, qualified_name: str) -> None:
        self._created_tables.append(qualified_name)

    def teardown(self) -> None:
        for qualified_name in reversed(self._created_tables):
            self._conn.cursor().execute(f"drop table if exists {qualified_name}")
        for schema in reversed(self._created_schemas):
            self._conn.cursor().execute(f"drop schema if exists {schema} cascade")
