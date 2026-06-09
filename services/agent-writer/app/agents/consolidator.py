"""ConsolidatorAgent:把多个 chapter drafts 合并成一个(纯逻辑,不调 LLM)。

输入来自 book_settings:
- chapters: list[str | dict]  # 章节正文列表;dict 时取 dict["content"]
- separator: str (可选,默认 '\\n\\n---\\n\\n')
- include_titles: bool (可选,默认 False)

输出:
  {"merged": "<合并后全文>", "total_chapters": <N>, "total_words": <字数>}
"""
from __future__ import annotations

import logging

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent

log = logging.getLogger(__name__)


@register_agent
class ConsolidatorAgent(BaseAgent):
    name = "ConsolidatorAgent"
    version = "1.0.0"
    capabilities = ["chapter_consolidation"]
    memory_layers = []  # 纯逻辑

    async def run(self, input: AgentInput) -> AgentOutput:
        chapters = input.book_settings.get("chapters", []) or []
        separator = input.book_settings.get("separator", "\n\n---\n\n")
        include_titles = bool(input.book_settings.get("include_titles", False))

        if not chapters:
            return AgentOutput(
                status="ok",
                result={"merged": "", "total_chapters": 0, "total_words": 0},
            )

        parts: list[str] = []
        for idx, ch in enumerate(chapters, start=1):
            if isinstance(ch, dict):
                content = ch.get("content", "") or ""
                title = ch.get("title", "") if include_titles else ""
                if title:
                    parts.append(f"# {title}\n\n{content}")
                else:
                    parts.append(content)
            else:
                parts.append(str(ch))

        merged = separator.join(parts)
        return AgentOutput(
            status="ok",
            result={
                "merged": merged,
                "total_chapters": len(chapters),
                "total_words": len(merged),
            },
        )
