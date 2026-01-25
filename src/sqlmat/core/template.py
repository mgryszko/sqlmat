from jinja2 import Environment


class TemplateEngine:
    def __init__(self):
        self.env = Environment()

    def render(self, sql: str, context: dict) -> str:
        template = self.env.from_string(sql)
        return template.render(context)

    def create_context(self, params: dict, target_table: str) -> dict:
        context = params.copy()
        context["this"] = target_table
        return context
