"""ShortFictionWriterAgent:短篇专用写作 agent(详见 v2 §1.2)。

与 WriterAgent 类似,但:
- 字数目标更长:默认 8000(可由 length_governance.target_short_fiction_words 覆盖)
- 模板用 short_fiction_writer.j2
- 仅 procedural 记忆(无 episodic,短篇通常一次性)
"""
from __future__ import annotations

import logging

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent
from minbook_common.models import LLMChatRequest

log = logging.getLogger(__name__)


@register_agent
class ShortFictionWriterAgent(BaseAgent):
    name = "ShortFictionWriterAgent"
    version = "1.0.0"
    capabilities = ["short_fiction_writing"]
    memory_layers = ["procedural"]

    async def run(self, input: AgentInput) -> AgentOutput:
        # 1. 加载文风模板(可选)
        style_template = ""
        try:
            style_template = (
                await self.load_procedural("short_fiction.style_template")
            ) or ""
        except Exception as e:  # noqa: BLE001
            log.warning("ShortFictionWriterAgent: load_procedural failed: %s", e)

        length_gov = input.book_settings.get("length_governance", {}) or {}
        target = int(
            length_gov.get("target_short_fiction_words")
            or length_gov.get("target_chapter_words", 8000)
        )
        min_w = int(length_gov.get("min_short_fiction_words", int(target * 0.85)))
        max_w = int(length_gov.get("max_short_fiction_words", int(target * 1.15)))

        prompt = self.prompts.render(
            "short_fiction_writer.j2",
            current_focus=input.current_focus,
            book_settings=input.book_settings,
            style_template=style_template,
            target_words=target,
        )

        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=12000,  # 短篇可能更长
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            node_id=input.node_id,
            agent_id=self.name,
        )

        draft_content = response.content
        word_count = len(draft_content)

        needs_length_normalization = word_count < min_w or word_count > max_w

        return AgentOutput(
            status="ok",
            result={
                "draft_content": draft_content,
                "word_count": word_count,
                "needs_length_normalization": needs_length_normalization,
                "target_words": target,
                "min_words": min_w,
                "max_words": max_w,
            },
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
