"""LengthNormalizer:字数偏离时压缩或扩展(详见 v2 §1.2)。

逻辑:
- 偏离 < 5% → 不处理,返 adjusted=False
- 偏离 ≥ 5% → 调 LLM(gpt-4o-mini,便宜模型),压缩或扩展到 target_words

输入支持两种:
1. LengthNormalizerInput(content, target_words, direction)
2. 裸 AgentInput.book_settings 里带 content / target_words / direction
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


class LengthNormalizerInput(AgentInput):
    content: str = ""
    target_words: int = 0
    direction: str = "compress"  # compress | expand


@register_agent
class LengthNormalizer(BaseAgent):
    name = "LengthNormalizer"
    version = "1.0.0"
    capabilities = ["length_normalization"]
    memory_layers = []  # 纯逻辑 / 偶尔调 LLM,无私有记忆层

    async def run(self, input: AgentInput) -> AgentOutput:
        content = (
            getattr(input, "content", "")
            or input.book_settings.get("content", "")
        )
        target_words = int(
            getattr(input, "target_words", 0)
            or input.book_settings.get("target_words", 0)
        )
        direction = (
            getattr(input, "direction", "")
            or input.book_settings.get("direction", "")
        )

        if not content or not target_words:
            return AgentOutput(
                status="error",
                error="LengthNormalizer: missing 'content' or 'target_words'",
            )

        current_words = len(content)
        diff = target_words - current_words
        ratio = abs(diff) / max(current_words, 1)

        # 偏离 < 5% 不处理
        if ratio < 0.05:
            return AgentOutput(
                status="ok",
                result={
                    "content": content,
                    "adjusted": False,
                    "current_words": current_words,
                    "target_words": target_words,
                    "ratio": ratio,
                },
            )

        # 自动判 direction(若未传)
        if not direction:
            direction = "expand" if diff > 0 else "compress"

        prompt = self.prompts.render(
            "length_normalizer.j2",
            content=content,
            current_words=current_words,
            target_words=target_words,
            direction=direction,
            diff=diff,
            abs_diff=abs(diff),
        )

        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o-mini",  # 字数调整用便宜模型
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=8000,
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            node_id=input.node_id,
            agent_id=self.name,
        )

        new_content = response.content
        return AgentOutput(
            status="ok",
            result={
                "content": new_content,
                "adjusted": True,
                "current_words": current_words,
                "target_words": target_words,
                "new_word_count": len(new_content),
                "direction": direction,
            },
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
