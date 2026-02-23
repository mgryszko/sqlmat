# sqlmat

A lightweight SQL transformation library inspired by dbt. Supports single SQL transformations with parameterized templates, targeting AWS Athena, AWS Redshift, DuckDB, and PostgreSQL. 

## Copy

The `Copy` transformation loads data from files into a table. Use the `options` attribute to pass adapter-specific options to the underlying copy command.

### CSV header handling

When the source CSV file contains a header row, you must tell the adapter to skip it via `options`. Each adapter has its own syntax:

**Athena** — pass as a `tblproperties` entry on the external table:

```python
class MyCopy(Copy):
    source = "s3://bucket/prefix/"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    columns = [("user_id", "bigint"), ("event_date", "string"), ("event_count", "bigint")]
    options = ["'skip.header.line.count'='1'"]
```

**Redshift** — use the `IGNOREHEADER` clause:

```python
class MyCopy(Copy):
    source = "s3://bucket/prefix/"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    columns = [("user_id", "bigint"), ("event_date", "varchar(10)"), ("event_count", "bigint")]
    options = ["IAM_ROLE 'arn:aws:iam::123456789:role/MyRole'", "IGNOREHEADER 1"]
```

**PostgreSQL** — use the `header` option in the `COPY WITH` clause:

```python
class MyCopy(Copy):
    source = "/path/to/data.csv"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    columns = [("user_id", "bigint"), ("event_date", "varchar"), ("event_count", "bigint")]
    options = ["header"]
```

**DuckDB** — pass `header=true` or `header=false` to `read_csv`:

```python
class MyCopy(Copy):
    source = "/path/to/data.csv"
    target_schema = "myschema"
    target_table = "events"
    format = "csv"
    options = ["header=true"]
```
