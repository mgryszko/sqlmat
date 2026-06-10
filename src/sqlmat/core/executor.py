from sqlmat.adapters.base import Adapter
from sqlmat.core.events import (
    CopyCompleted,
    CopyFailed,
    CopyStarted,
    EventHandler,
    SqlRendered,
    TransformationCompleted,
    TransformationFailed,
    TransformationStarted,
    UnloadCompleted,
    UnloadFailed,
    UnloadStarted,
    noop_handler,
)
from sqlmat.core.template import TemplateEngine
from sqlmat.core.transformation import (
    Copy,
    FullRefreshTableTransformation,
    IncrementalTableTransformation,
    Unload,
)


class Executor:
    """Orchestrates transformation execution against a database adapter.

    Renders Jinja2 SQL templates, manages the drop-and-recreate lifecycle, and emits
    structured events for logging and monitoring.
    """

    def __init__(self, adapter: Adapter, event_handler: EventHandler = noop_handler):
        self._adapter = adapter
        self._template_engine = TemplateEngine()
        self._event_handler = event_handler

    def run(
        self,
        operation: FullRefreshTableTransformation | IncrementalTableTransformation | Unload | Copy,
        template_context: dict | None = None,
    ) -> None:
        """Run a transformation, unload, or copy operation.

        Args:
            operation: The operation to execute.
            template_context: Optional dict of Jinja2 template parameters merged with implicit parameters.
        """
        if template_context is None:
            template_context = {}

        if isinstance(operation, FullRefreshTableTransformation):
            self._execute_table_transformation(operation, template_context)
        elif isinstance(operation, IncrementalTableTransformation):
            self._execute_table_transformation(operation, template_context)
        elif isinstance(operation, Unload):
            self._run_unload(operation, template_context)
        elif isinstance(operation, Copy):
            self._run_copy(operation)

    def _execute_table_transformation(
        self,
        transformation: FullRefreshTableTransformation | IncrementalTableTransformation,
        template_context: dict,
    ) -> None:
        target_schema = transformation.target_schema
        target_table = transformation.target_table
        sql = transformation.sql

        if isinstance(transformation, IncrementalTableTransformation):
            materialization = transformation.strategy
            unique_key = transformation.unique_key
            incremental_predicates = transformation.incremental_predicates
        else:
            materialization = "full_refresh"
            unique_key = None
            incremental_predicates = None

        self._emit(TransformationStarted(target_schema, target_table, materialization))

        rendered_sql = self._template_engine.render(sql, template_context | {"target_table": transformation.full_table_name})

        self._emit(SqlRendered(sql=rendered_sql, target_schema=target_schema, target_table=target_table))

        try:
            if materialization == "delete_insert":
                self._run_delete_insert(target_schema, target_table, rendered_sql, unique_key, incremental_predicates)
            elif materialization == "merge":
                self._run_merge(target_schema, target_table, rendered_sql, unique_key, incremental_predicates)
            else:
                self._run_full_refresh(target_schema, target_table, rendered_sql)
            self._emit(TransformationCompleted(target_schema, target_table, materialization))
        except Exception as e:
            self._emit(
                TransformationFailed(error=e, target_schema=target_schema, target_table=target_table, materialization=materialization)
            )
            raise

    def _run_full_refresh(self, target_schema: str, target_table: str, rendered_sql: str) -> None:
        self._adapter.begin_transaction()
        try:
            self._adapter.drop_table(target_schema, target_table)
            self._adapter.create_table_as(target_schema, target_table, rendered_sql)
            self._adapter.commit()
        except Exception:
            self._adapter.rollback()
            raise

    def _run_delete_insert(
        self,
        target_schema: str,
        target_table: str,
        rendered_sql: str,
        unique_key: str | list[str] | None,
        incremental_predicates: str | list[str] | None = None,
    ) -> None:
        if unique_key is None:
            raise ValueError("unique_key is required for delete_insert materialization")

        temp_table = f"{target_table}_tmp"
        temp_table_full = f"{target_schema}.{temp_table}"

        self._adapter.begin_transaction()
        try:
            self._adapter.drop_table(target_schema, temp_table)
            self._adapter.create_table_as(target_schema, temp_table, rendered_sql)

            if not self._adapter.table_exists(target_schema, target_table):
                self._adapter.rename_table(target_schema, temp_table, target_table)
                self._adapter.commit()
                return

            columns = self._adapter.get_columns(target_schema, target_table)

            predicates = self._normalize_predicates(incremental_predicates)

            if isinstance(unique_key, list):
                self._adapter.delete_with_using(target_schema, target_table, temp_table_full, unique_key, predicates)
            else:
                self._adapter.delete_with_in(target_schema, target_table, temp_table_full, unique_key, predicates)

            self._adapter.insert_from_select(target_schema, target_table, columns, temp_table_full)

            self._adapter.drop_table(target_schema, temp_table)
            self._adapter.commit()
        except Exception:
            self._adapter.rollback()
            raise

    def _run_merge(
        self,
        target_schema: str,
        target_table: str,
        rendered_sql: str,
        unique_key: str | list[str] | None,
        incremental_predicates: str | list[str] | None = None,
    ) -> None:
        if unique_key is None:
            raise ValueError("unique_key is required for merge materialization")

        self._adapter.begin_transaction()
        try:
            if not self._adapter.table_exists(target_schema, target_table):
                self._adapter.create_table_as(target_schema, target_table, rendered_sql)
                self._adapter.commit()
                return

            predicates = self._normalize_predicates(incremental_predicates)
            unique_keys = [unique_key] if isinstance(unique_key, str) else unique_key

            self._adapter.merge(target_schema, target_table, rendered_sql, unique_keys, predicates)
            self._adapter.commit()
        except Exception:
            self._adapter.rollback()
            raise

    def _run_unload(self, unload: Unload, template_context: dict) -> None:
        destination = unload.destination
        fmt = unload.format
        sql = unload.sql
        options = unload.options

        self._emit(UnloadStarted(destination, fmt))

        rendered_sql = self._template_engine.render(sql, template_context)

        self._emit(SqlRendered(sql=rendered_sql))

        try:
            self._adapter.copy_to(rendered_sql, destination, fmt, options)
            self._emit(UnloadCompleted(destination, fmt))
        except Exception as e:
            self._emit(UnloadFailed(error=e, destination=destination, format=fmt))
            raise

    def _run_copy(self, copy: Copy) -> None:
        source = copy.source
        schema = copy.target_schema
        table = copy.target_table
        fmt = copy.format
        columns = copy.columns
        options = copy.options

        self._emit(CopyStarted(source, schema, table, fmt))
        try:
            self._adapter.begin_transaction()
            try:
                self._adapter.drop_table(schema, table)
                self._adapter.copy_from(source, schema, table, fmt, columns, options)
                self._adapter.commit()
            except Exception:
                self._adapter.rollback()
                raise
            self._emit(CopyCompleted(source, schema, table, fmt))
        except Exception as e:
            self._emit(CopyFailed(error=e, source=source, target_schema=schema, target_table=table, format=fmt))
            raise

    def _normalize_predicates(self, predicates: str | list[str] | None) -> list[str] | None:
        if predicates is None:
            return None
        if isinstance(predicates, str):
            return [predicates]
        return predicates

    def _emit(self, event):
        self._event_handler(event)
