from sqlmat.adapters.base import Adapter
from sqlmat.core.template import TemplateEngine
from sqlmat.core.transformation import Transformation


class Executor:
    def __init__(self, adapter: Adapter):
        self.adapter = adapter
        self.template_engine = TemplateEngine()

    def run(self, transformation: Transformation, params: dict | None = None) -> None:
        if params is None:
            params = {}

        target_schema = transformation.target_schema
        target_table = transformation.target_table
        sql = transformation.sql
        materialization = transformation.materialization
        unique_key = transformation.unique_key
        incremental_predicates = transformation.incremental_predicates

        full_table_name = transformation.get_full_table_name()
        context = self.template_engine.create_context(params, full_table_name)
        rendered_sql = self.template_engine.render(sql, context)

        if materialization == "delete_insert":
            self._run_delete_insert(target_schema, target_table, rendered_sql, unique_key, incremental_predicates)
        else:
            self._run_full_refresh(target_schema, target_table, rendered_sql)

    def _run_full_refresh(self, target_schema: str, target_table: str, rendered_sql: str) -> None:
        self.adapter.drop_table(target_schema, target_table)
        self.adapter.create_table_as(target_schema, target_table, rendered_sql)

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

        self.adapter.drop_table(target_schema, temp_table)
        self.adapter.create_table_as(target_schema, temp_table, rendered_sql)

        if not self.adapter.table_exists(target_schema, target_table):
            self.adapter.execute(f"alter table {temp_table_full} rename to {target_table}")
            return

        columns = self.adapter.get_columns(target_schema, target_table)

        predicates = self._normalize_predicates(incremental_predicates)

        if isinstance(unique_key, list):
            self.adapter.delete_with_using(target_schema, target_table, temp_table_full, unique_key, predicates)
        else:
            self.adapter.delete_with_in(target_schema, target_table, temp_table_full, unique_key, predicates)

        self.adapter.insert_from_select(target_schema, target_table, columns, temp_table_full)

        self.adapter.drop_table(target_schema, temp_table)

    def _normalize_predicates(self, predicates: str | list[str] | None) -> list[str] | None:
        if predicates is None:
            return None
        if isinstance(predicates, str):
            return [predicates]
        return predicates
