"""StyleAnalyzer:从样本文抽取文风指纹(详见 v2 §2 风格语料库)。

流程:
1. 调 LLM(gpt-4o)抽取 fingerprint:句长 / 标点风格 / 词汇偏好 / 节奏 / 隐喻
2. 解析 JSON
3. **写 writer.style_corpus 表**(用 self.memory._pool;writer 自己的 schema)
   - 表已在 alembic 0001 中创建:
     CREATE TABLE writer.style_corpus (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       book_id UUID NOT NULL,
       fingerprint_json JSONB NOT NULL,
       source VARCHAR(50),
       embedding VECTOR,
       created_at TIMESTAMPTZ DEFAULT NOW()
     )

降级:
- LLM 解析失败 → status=error
- DB 写失败 → warning log + 继续(fingerprint 已生成)
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent
from minbook_common.models import LLMChatRequest

log = logging.getLogger(__name__)


@register_agent
class StyleAnalyzer(BaseAgent):
    name = "StyleAnalyzer"
    version = "1.0.0"
    capabilities = ["style_analysis", "fingerprint_extraction"]
    memory_layers = ["semantic"]  # 文风指纹 → semantic

    async def run(self, input: AgentInput) -> AgentOutput:
        sample_text = input.book_settings.get("sample_text", "") or ""
        source = input.book_settings.get("source", "analyzed")

        if not sample_text:
            return AgentOutput(
                status="error",
                error="StyleAnalyzer: missing 'sample_text'",
            )

        prompt = self.prompts.render(
            "style_analyzer.j2", sample_text=sample_text,
        )

        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000,
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            agent_id=self.name,
        )

        try:
            fingerprint = json.loads(response.content)
        except Exception as e:  # noqa: BLE001
            log.warning("StyleAnalyzer: JSON parse failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"JSON parse failed: {e}",
            )

        # 写 writer.style_corpus(失败优雅降级)
        await self._persist_fingerprint(
            book_id=input.book_id,
            fingerprint=fingerprint,
            source=source,
        )

        return AgentOutput(
            status="ok",
            result=fingerprint,
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )

    async def _persist_fingerprint(
        self,
        book_id: UUID,
        fingerprint: dict,
        source: str,
    ) -> None:
        """写 writer.style_corpus,失败仅 warning。"""
        try:
            pool = self.memory.pool  # raises if _pool is None
        except Exception as e:  # noqa: BLE001
            log.warning("StyleAnalyzer: memory.pool unavailable: %s", e)
            return

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO writer.style_corpus
                       (book_id, fingerprint_json, source)
                       VALUES ($1, $2, $3)""",
                    book_id,
                    json.dumps(fingerprint),
                    source,
                )
        except Exception as e:  # noqa: BLE001
            log.warning("StyleAnalyzer: writer.style_corpus insert failed: %s", e)
