# sqlmat

A lightweight SQL transformation library inspired by dbt, focused on simplicity. sqlmat enables single SQL transformations with parameterized Jinja2 templates, targeting DuckDB, PostgreSQL, AWS Redshift, and AWS Athena.

## Installation

```bash
uv add sqlmat
```

To upgrade:

```bash
uv lock --upgrade-package sqlmat
```

### Database drivers

sqlmat works with standard DB-API 2.0 connections. Install the driver for your database:

| Database   | Tested drivers                              |
|------------|---------------------------------------------|
| DuckDB     | `duckdb`                                    |
| PostgreSQL | `psycopg2`, `psycopg` (psycopg 3)           |
| Redshift   | `redshift-connector`, `psycopg2`, `psycopg` |
| Athena     | `pyathena`                                  |

## Transformations

### FullRefreshTableTransformation

Drops and recreates the target table on every run.

```python
from sqlmat import Executor, FullRefreshTableTransformation
from sqlmat.adapters import DuckDBAdapter

class MyTransformation(FullRefreshTableTransformation):
    target_schema = "analytics"
    target_table = "users"
    sql = "select id, name from raw.users where active = {{ is_active }}"

executor = Executor(DuckDBAdapter(conn))
executor.run(MyTransformation(), template_context={"is_active": "true"})
```

Implicit template parameter:
- `{{ target_table }}` - resolves to `<target_schema>.<target_table>` (e.g. `analytics.users`)

Any additional parameters can be passed via the `template_context` dict.

### IncrementalTableTransformation

Updates the target table incrementally using either `delete_insert` or `merge` strategy.

```python
from sqlmat import IncrementalTableTransformation

class MyIncremental(IncrementalTableTransformation):
    target_schema = "analytics"
    target_table = "events"
    sql = "select * from raw.events where updated_at > '2024-01-01'"
    strategy = "delete_insert"  # or "merge"
    unique_key = "event_id"  # str or list[str]
    incremental_predicates = None  # optional str or list[str]
```

Implicit template parameter:
- `{{ target_table }}` - resolves to `<target_schema>.<target_table>`

If the target table does not exist yet, it is created from the query result. On subsequent runs, the strategy determines how rows are merged:
- `delete_insert` - deletes matching rows by `unique_key` (with optional `incremental_predicates`), then inserts new rows
- `merge` - uses SQL `MERGE` to upsert rows by `unique_key`

### Unload

Exports query results to a file or external storage.

```python
from sqlmat import Unload

unload = Unload()
unload.sql = "select * from analytics.users"
unload.destination = "s3://bucket/path/"
unload.format = "parquet"  # "parquet", "csv", or "json"
unload.options = ["ALLOWOVERWRITE"]  # optional, adapter-specific

executor.run(unload)
```

The `sql` field supports Jinja2 templates with parameters passed via `template_context`. No implicit template parameters.

### Copy

Loads data from a file or external storage into a table. The target table is dropped and recreated on every run.

```python
from sqlmat import Copy

copy = Copy()
copy.source = "s3://bucket/path/"
copy.target_schema = "raw"
copy.target_table = "events"
copy.format = "parquet"  # "parquet", "csv", or "json"
copy.columns = [("id", "integer"), ("name", "varchar")]  # required for Athena, Redshift, PostgreSQL
copy.options = ["IGNOREHEADER 1"]  # optional, adapter-specific
```

No template rendering is applied to Copy.

#### CSV header handling

When the source CSV file contains a header row, you must tell the adapter to skip it via `options`. Each adapter has its own syntax:

**Athena** - pass as a `tblproperties` entry on the external table:

```python
class MyCopy(Copy):
    source = "s3://bucket/prefix/"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    columns = [("user_id", "bigint"), ("event_date", "string"), ("event_count", "bigint")]
    options = ["'skip.header.line.count'='1'"]
```

**Redshift** - use the `IGNOREHEADER` clause:

```python
class MyCopy(Copy):
    source = "s3://bucket/prefix/"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    columns = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]
    options = ["IAM_ROLE 'arn:aws:iam::123456789:role/MyRole'", "IGNOREHEADER 1"]
```

**PostgreSQL** - use the `header` option in the `COPY WITH` clause:

```python
class MyCopy(Copy):
    source = "/path/to/data.csv"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    columns = [("user_id", "bigint"), ("event_date", "varchar"), ("event_count", "bigint")]
    options = ["header"]
```

**DuckDB** - pass `header=true` or `header=false` to `read_csv`:

```python
class MyCopy(Copy):
    source = "/path/to/data.csv"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    options = ["header=true"]
```

## Adapters

All adapters implement the same `Adapter` interface and accept a DB-API 2.0 connection.

### DuckDBAdapter

```python
from sqlmat.adapters import DuckDBAdapter

adapter = DuckDBAdapter(conn)
```

- Copy supports `parquet`, `csv`, and `json` formats using DuckDB's `read_parquet`/`read_csv`/`read_json`
- Unload uses DuckDB's `COPY ... TO` syntax
- `columns` parameter is not required for Copy (DuckDB infers schema)

### PostgresAdapter

```python
from sqlmat.adapters import PostgresAdapter

adapter = PostgresAdapter(conn)
```

- Copy and Unload only support `csv` format
- Copy reads from local files via `COPY ... FROM STDIN`
- Unload writes to local files via `COPY ... TO STDOUT`
- Compatible with both psycopg2 (`copy_expert`) and psycopg 3 (`cursor.copy`)

### RedshiftAdapter

```python
from sqlmat.adapters import RedshiftAdapter

adapter = RedshiftAdapter(conn)
```

- Copy uses Redshift's `COPY` command (supports `parquet`, `csv`, `json`)
- Unload uses Redshift's `UNLOAD` command
- `columns` parameter is required for Copy
- Pass IAM credentials, region, and other Redshift-specific options via `options`

### AthenaAdapter

```python
from sqlmat.adapters import AthenaAdapter

adapter = AthenaAdapter(conn, s3_table_base_uri="s3://bucket/tables/")
```

- Requires `s3_table_base_uri` to specify where Iceberg tables are stored
- Creates Iceberg tables with Parquet storage format
- Copy creates a temporary external table over the source, then CTAS into an Iceberg table
- `columns` parameter is required for Copy
- Transactions are no-ops (Athena does not support transactions)

## Logging

sqlmat uses an event-based logging system. The `Executor` and each `Adapter` accept an `event_handler` callback (`Callable[[Event], None]`) that receives structured event objects for every operation.

Events include: `TransformationStarted`, `TransformationCompleted`, `TransformationFailed`, `SqlRendered`, `UnloadStarted`, `UnloadCompleted`, `UnloadFailed`, `CopyStarted`, `CopyCompleted`, `CopyFailed`, `TableCreated`, `TableDropped`, `SqlExecuted`, `DataLoaded`, `DataUnloaded`, `RowsDeleted`, `RowsInserted`, `RowsMerged`, `TransactionBegun`, `TransactionCommitted`, `TransactionRolledBack`, `TableExistenceChecked`.

### PythonLoggingSink

A built-in event handler that routes events to Python's `logging` module:

```python
from sqlmat import Executor, PythonLoggingSink
from sqlmat.adapters import DuckDBAdapter

sink = PythonLoggingSink()  # uses logging.getLogger("sqlmat") by default
adapter = DuckDBAdapter(conn, event_handler=sink)
executor = Executor(adapter, event_handler=sink)
```

High-level events (`TransformationStarted/Completed/Failed`, `CopyStarted/Completed/Failed`, `UnloadStarted/Completed/Failed`) are logged at `INFO`/`ERROR` level. Low-level SQL events are logged at `DEBUG`.

### Custom event handler

```python
from sqlmat.core.events import TransformationCompleted

def my_handler(event):
    match event:
        case TransformationCompleted(target_schema=s, target_table=t):
            print(f"Done: {s}.{t}")

executor = Executor(adapter, event_handler=my_handler)
```

## Test framework

sqlmat provides test utilities in `sqlmat.test` for writing integration tests against real databases.

### Optional dependencies

Install the `test` extra for the testing utilities:

```bash
uv add sqlmat[test]
```

This includes:
- `approvaltests` - for approval-based assertions on exported files (parquet, CSV, JSON)
- `fsspec` - for reading files from local or remote filesystems in approval tests
- `polars` - for reading and comparing Parquet files in approval tests

These are needed only when using `Files.approve_parquet`, `Files.approve_csv`, or `Files.approve_jsonl`.

### SchemaRegistry

Manages creation and teardown of test schemas and tracks created tables for cleanup:

```python
from sqlmat.test import SchemaRegistry

with SchemaRegistry(conn) as registry:
    schema = registry.create_schema(prefix="test")
    # ... run transformations targeting this schema ...
# schemas and registered tables are dropped automatically
```

### Table

Provides helpers for creating tables, inserting rows, and asserting on table contents. Database-specific subclasses: `DuckDBTable`, `PostgresTable`, `RedshiftTable`, `AthenaTable`.

```python
from sqlmat.test import DuckDBTable, SchemaRegistry

with SchemaRegistry(conn) as registry:
    schema = registry.create_schema()
    table = DuckDBTable(conn, schema, "users", [("id", "integer"), ("name", "varchar")])
    table.create(registry)
    table.insert([(1, "Alice"), (2, "Bob")])
    table.assert_table_equals([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
```

Rows can be inserted as tuples (positional) or dicts (by column name, with optional defaults).

### Files

Approval-test helpers for verifying exported file contents:

```python
from sqlmat.test import Files

Files("/path/to/output.parquet").approve_parquet(sort_columns=["id"])
Files("s3://bucket/output/*.csv").approve_csv(header=True, sort_columns=["id"])
Files("s3://bucket/output/*.jsonl").approve_jsonl(sort_columns=["id"])
```

### Transaction helpers

Context managers for wrapping test setup/teardown in transactions: `DuckDBTx`, `PostgresTx`, `RedshiftTx`.

```python
from sqlmat.test import DuckDBTx

with DuckDBTx(conn):
    table.insert([(1, "Alice")])
    # committed on success, rolled back on exception
```
