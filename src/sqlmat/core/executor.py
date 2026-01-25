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

        full_table_name = transformation.get_full_table_name()
        context = self.template_engine.create_context(params, full_table_name)
        rendered_sql = self.template_engine.render(sql, context)

        self.adapter.drop_table(target_schema, target_table)
        self.adapter.create_table_as(target_schema, target_table, rendered_sql)
