"""Jinja2 prompt 模板加载器。

模板存储位置:
- 文件模板:<service_dir>/prompts/<name>.j2(每个 agent 服务本地)
- 数据库模板:由 agent 通过 `memory_client.load_procedural(name)` 取 → `render_string(source, **vars)`

注:`.j2` / `.jinja` / `.txt` 文件默认 autoescape 关闭(因为 prompt 不是 HTML)。
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape


class PromptLoader:
    def __init__(self, template_dir: str | Path = "prompts") -> None:
        self.template_dir = str(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(
                disabled_extensions=("j2", "jinja", "txt"), default=False,
            ),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **vars) -> str:
        """渲染 templates/<template_name> 文件。"""
        template = self.env.get_template(template_name)
        return template.render(**vars)

    def render_string(self, source: str, **vars) -> str:
        """直接渲染字符串(用于从 DB 加载的 prompt)。"""
        return Template(source, autoescape=False).render(**vars)
