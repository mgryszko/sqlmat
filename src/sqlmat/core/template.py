from jinja2 import Environment


class TemplateEngine:
    def __init__(self):
        self.env = Environment()

    def render(self, sql: str, context: dict) -> str:
        template = self.env.from_string(sql)
        return template.render(context)
