# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

sqlmat is a lightweight SQL transformation library inspired by dbt, focused on simplicity. It enables single SQL transformations with parameterized templates, targeting AWS Athena, AWS Redshift, and DuckDB. Currently supports full-refresh mode only (no incremental loads).

## Development commands

### Testing

**IMPORTANT**: All changes must be verified by running all tests before considering the work complete.

- Use the testing framework from `sqlmat.test` (`SchemaRegistry`, `Table`, `ColumnSpec`). `SchemaRegistry` manages creation/teardown of test schemas and tracks created tables. `Table` provides helpers for creating tables, inserting rows, and asserting on table contents (`assert_table_equals`, `assert_table_contains`)
- Use plain functions, not test classes
- Prefer asserting on complete objects rather than individual properties
- Verify behavior through the public API (`Executor`, `Transformation`, `DuckDBAdapter`), not internal implementation details
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
- Base class for SQL transformations
- Defines `target_schema`, `target_table`, and `sql` attributes
- Users subclass this to define their transformations
- Instantiate transformations before passing to Executor

**Executor** (`src/sqlmat/core/executor.py`)
- Orchestrates the transformation execution
- Takes an instantiated `Transformation` object and optional `params` dict
- Renders SQL templates using Jinja2
- Executes drop-and-recreate pattern (full-refresh only)
- Uses the Adapter pattern for database operations

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
2. User calls `executor.run(transformation, params={"key": "value"})`
3. Executor extracts `target_schema`, `target_table`, `sql` from transformation
4. TemplateEngine renders SQL with params and `{{ this }}` variable
5. Adapter drops existing table (if exists)
6. Adapter creates new table with rendered SQL

### Coding conventions

- **Type all functions and methods**: Every function and method (including test functions, fixtures, and helpers) must have type annotations for all parameters and the return type

### Key design decisions

- **Instantiated transformations**: `executor.run()` accepts instances, not classes, giving users control over instantiation
- **Full-refresh only**: Always drop and recreate tables; no incremental loads yet
- **ABC-based adapters**: Using `ABC` with `@abstractmethod` for adapter interface
- **Single transformations**: No dependency graph or DAG execution
- **Minimal __init__.py files**: Only use `__init__.py` to define public API exports; internal packages (like `core`) don't need them
- **Adapter decoupled from transformations**: Adapter methods receive plain parameters (primitives, dicts), not transformation objects
- **Protected class members**: Class variables and methods not exposed to the outside world should be marked as class-protected with a single underscore prefix (e.g., `self._adapter`, `self._emit`)
