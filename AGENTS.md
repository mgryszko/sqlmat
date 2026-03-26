# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

sqlmat is a lightweight SQL transformation library inspired by dbt, focused on simplicity. It enables single SQL transformations with parameterized templates, targeting AWS Athena, AWS Redshift, and DuckDB. Currently supports full-refresh mode only (no incremental loads).

## Development commands

### Testing

**IMPORTANT**: All changes must be verified by running all tests (`uv run pytest -n auto`) before considering the work complete. Only run a single test file or a specific test when the change is very localized and unlikely to affect other parts of the codebase.

- Use the testing framework from `sqlmat.test` (`SchemaRegistry`, `Table`, `ColumnSpec`). `SchemaRegistry` manages creation/teardown of test schemas and tracks created tables. `Table` provides helpers for creating tables, inserting rows, and asserting on table contents (`assert_table_equals`, `assert_table_contains`). A `ColumnSpec` entry is either `(name, type)` or `(name, type, wrapper)` where `wrapper` is a SQL function template with `{}` as the placeholder (e.g., `("payload", "super", "json_parse({})")` for Redshift `super` columns)
- **Always use `Table.assert_table_equals` for table assertions** — never use raw cursor queries (`cursor.fetchall()`, `conn.execute(...).fetchall()`) to assert on table contents. For tables created by operations like Copy, create a `Table` object (without calling `.create()`) and use it for assertions
- Use plain functions, not test classes
- Prefer asserting on complete objects rather than individual properties
- Verify behavior through the public API (`Adapter.executor()`, `Transformation`, `DuckDBAdapter`), not internal implementation details
- Don't use underscore-prefixed (package-private) names in tests — no `_helper()` functions or `_CONSTANT` variables

```bash
# Run all tests (in parallel)
uv run pytest -n auto

# Run all tests (sequential, for debugging)
uv run pytest

# Run a specific test file
uv run pytest tests/test_sqlmat_duckdb.py

# Run a specific test
uv run pytest tests/test_sqlmat_duckdb.py::test_templated_transformation
```

**NOTE**: Tests should be executed in parallel using `pytest -n auto` for faster feedback. The `-n auto` flag automatically detects the number of CPU cores and runs tests in parallel. Use sequential execution (without `-n`) only when debugging.

### Linting
```bash
# Check code style
uv run ruff check

# Auto-fix issues
uv run ruff check --fix

# Format code
uv run ruff format
```

## Architecture

### Core components

**Transformation** (`src/sqlmat/core/transformation.py`)
- Frozen dataclasses: `FullRefreshTableTransformation`, `IncrementalTableTransformation`, `Unload`, `Copy`
- Instantiate directly with keyword arguments, e.g. `FullRefreshTableTransformation(target_schema=..., target_table=..., sql=...)`

**Executor** (`src/sqlmat/core/executor.py`)
- Orchestrates the transformation execution
- Created via `adapter.executor()`, which shares the adapter's event handler
- Takes an instantiated `Transformation` object and optional `params` dict
- Renders SQL templates using Jinja2
- Executes drop-and-recreate pattern (full-refresh only)
- Not part of the public API (`sqlmat.__init__`); used internally via the adapter

**TemplateEngine** (`src/sqlmat/core/template.py`)
- Wraps Jinja2 for SQL template rendering
- Provides `{{ this }}` variable automatically (references target table)
- Merges user params with built-in variables

**Adapter** (`src/sqlmat/adapters/base.py`)
- Abstract base class defining database operations: `execute`, `create_table_as`, `drop_table`
- Implementations exist for DuckDB (only)
- Future: AWS Athena, AWS Redshift

### Execution flow

1. User instantiates a `Transformation` subclass
2. User calls `adapter.executor().run(transformation, params={"key": "value"})`
3. Executor extracts `target_schema`, `target_table`, `sql` from transformation
4. TemplateEngine renders SQL with params and `{{ this }}` variable
5. Adapter drops existing table (if exists)
6. Adapter creates new table with rendered SQL

### Coding conventions

- **Type all functions and methods**: Every function and method (including test functions, fixtures, and helpers) must have type annotations for all parameters and the return type
- **SQL keywords, types, and function names**: Always use lowercase for SQL keywords (`select`, `from`, `create table`), data types (`integer`, `varchar`), and function names (`read_parquet`, `lower`). This applies to both production code and tests. Exception: user-provided options and format specifiers may use uppercase when required by the database (e.g., `fmt.upper()` for format values)
- **SQL dialect awareness**: When writing SQL queries, always confirm the target database engine (Redshift, Athena, PostgreSQL, DuckDB) before writing. Use only functions and syntax available in that specific engine

### Working practices

- **Investigation before modification**: For investigation/exploration tasks, avoid making permanent code changes unless explicitly asked. Present findings as a summary or plan document first

### Key design decisions

- **Frozen dataclass transformations**: All transformation types are frozen dataclasses instantiated directly with keyword arguments
- **Full-refresh only**: Always drop and recreate tables; no incremental loads yet
- **ABC-based adapters**: Using `ABC` with `@abstractmethod` for adapter interface
- **Single transformations**: No dependency graph or DAG execution
- **Minimal __init__.py files**: Only use `__init__.py` to define public API exports; internal packages (like `core`) don't need them
- **Adapter decoupled from transformations**: Adapter methods receive plain parameters (primitives, dicts), not transformation objects
- **Protected members**: Class variables, methods, and module-level functions not exposed to the outside world should be marked with a single underscore prefix (e.g., `self._adapter`, `self._emit`, `def _helper()`)
