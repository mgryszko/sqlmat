# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

sqlmat is a lightweight SQL transformation library inspired by dbt, focused on simplicity. It enables single SQL transformations with parameterized templates, targeting AWS Athena, AWS Redshift, and DuckDB. Currently supports full-refresh mode only (no incremental loads).

## Development commands

### Testing

**IMPORTANT**: All changes must be verified by running all tests before considering the work complete.

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_sqlmat_duckdb.py

# Run a specific test
uv run pytest tests/test_sqlmat_duckdb.py::test_templated_transformation
```

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

### Key design decisions

- **Instantiated transformations**: `executor.run()` accepts instances, not classes, giving users control over instantiation
- **Full-refresh only**: Always drop and recreate tables; no incremental loads yet
- **ABC-based adapters**: Using `ABC` with `@abstractmethod` for adapter interface
- **Single transformations**: No dependency graph or DAG execution
- **Plain pytest functions**: Tests use plain functions, not test classes, for simplicity
- **Minimal __init__.py files**: Only use `__init__.py` to define public API exports; internal packages (like `core`) don't need them
- **Public API testing only**: Tests verify behavior through the public API (`Executor`, `Transformation`, `DuckDBAdapter`), not internal implementation details
- **Full-object assertions**: Prefer asserting on complete objects rather than individual properties for more maintainable and comprehensive tests
