"""WriterAgent:基于编排后的上下文生成正文 + 字数治理(详见 v2 §1.2)。

流程:
1. recall 风格语料(episodic):查询历史章节相似文风
2. load_procedural(writer.style_template):加载文风模板(若有)
3. 渲染 prompts/writer.j2(字数目标从 length_governance 取)
4. 调 LLM(gpt-4o, max_tokens=8000)
5. **字数治理**:检查 word_count ∈ [min, max],偏离标 needs_length_normalization=True
6. store_episode(为未来 recall)

字数治理:
- target_chapter_words / min_chapter_words / max_chapter_words 来自 length_governance
- min/max 默认值:target * 0.85 / target * 1.15
- 偏离 → result["needs_length_normalization"] = True(由 pipeline 在下一步调 LengthNormalizer)
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent
from minbook_common.models import LLMChatRequest

log = logging.getLogger(__name__)


class WriterInput(AgentInput):
    """WriterAgent 输入(支持 compiled_context + rule_stack)。"""

    compiled_context: dict = {}  # 来自 ComposerAgent
    rule_stack: list[str] = []


@register_agent
class WriterAgent(BaseAgent):
    name = "WriterAgent"
    version = "1.0.0"
    capabilities = ["chapter_drafting", "word_count_governance"]
    memory_layers = ["episodic", "semantic", "procedural"]

    async def run(self, input: AgentInput) -> AgentOutput:
        # 上层调用既可能传 WriterInput 也可能传裸 AgentInput,二者兼容
        compiled_context = getattr(input, "compiled_context", {}) or {}
        rule_stack = getattr(input, "rule_stack", []) or []
        if not compiled_context and isinstance(input.book_settings, dict):
            compiled_context = input.book_settings.get("compiled_context", {}) or {}
        if not rule_stack and isinstance(input.book_settings, dict):
            rule_stack = input.book_settings.get("rule_stack", []) or []

        # 1. Recall 风格语料(失败优雅降级)
        style_corpus: list[dict] = []
        try:
            style_corpus = await self.recall_context(
                book_id=input.book_id,
                query=f"writing style for {input.book_settings.get('genre', '')}",
                top_k=3,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("WriterAgent: recall_context failed: %s", e)

        # 2. load_procedural(writer.style_template)
        style_template = ""
        try:
            style_template = (await self.load_procedural("writer.style_template")) or ""
        except Exception as e:  # noqa: BLE001
            log.warning("WriterAgent: load_procedural failed: %s", e)

        # 3. 渲染 prompt
        prompt = self.prompts.render(
            "writer.j2",
            compiled_context=compiled_context,
            rule_stack=rule_stack,
            style_corpus=style_corpus,
            style_template=style_template,
            book_settings=input.book_settings,
        )

        # 4. 调 LLM
        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=8000,
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            node_id=input.node_id,
            agent_id=self.name,
        )

        draft_content = response.content
        word_count = len(draft_content)

        # 5. 字数治理
        length_gov = input.book_settings.get("length_governance", {}) or {}
        target = int(length_gov.get("target_chapter_words", 3000))
        min_w = int(length_gov.get("min_chapter_words", int(target * 0.85)))
        max_w = int(length_gov.get("max_chapter_words", int(target * 1.15)))

        needs_length_normalization = word_count < min_w or word_count > max_w

        # 6. Store episode(失败优雅降级)
        try:
            await self.store_episode(
                book_id=input.book_id,
                episode={
                    "chapter_number": compiled_context.get("chapter_number"),
                    "word_count": word_count,
                    "draft_excerpt": draft_content[:200],
                },
            )
        except Exception as e:  # noqa: BLE001
            log.warning("WriterAgent: store_episode failed: %s", e)

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
