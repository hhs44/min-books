"""ChapterAnalyzerAgent:分析章节(情感曲线 / 节奏 / 关键词,详见 v2 §1.2)。

输入:
- book_settings.content: str  # 章节正文

调 LLM(gpt-4o, max_tokens=2000),返 JSON:
  {"emotional_arc": "...", "pacing_score": 0.0-1.0, "key_themes": [...],
   "key_characters": [...], "summary": "..."}

JSON 解析失败 → status=error。
"""
from __future__ import annotations

import json
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
class ChapterAnalyzerAgent(BaseAgent):
    name = "ChapterAnalyzerAgent"
    version = "1.0.0"
    capabilities = ["chapter_analysis"]
    memory_layers = []

    async def run(self, input: AgentInput) -> AgentOutput:
        content = input.book_settings.get("content", "") or ""
        if not content:
            return AgentOutput(
                status="error",
                error="ChapterAnalyzerAgent: missing 'content'",
            )

        prompt = self.prompts.render("chapter_analyzer.j2", content=content)

        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            agent_id=self.name,
        )

        try:
            result = json.loads(response.content)
        except Exception as e:  # noqa: BLE001
            log.warning("ChapterAnalyzerAgent: JSON parse failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"JSON parse failed: {e}",
            )

        return AgentOutput(
            status="ok",
            result=result,
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
