"""ReviserAgent:根据 audit issues 修复章节(详见 v2 §1.2)。

流程:
1. 接收 content + issues
2. 渲染 prompts/reviser.j2
3. 调 LLM(gpt-4o, max_tokens=8000)
4. 解析 JSON → revised_content + change_log
5. 返 AgentOutput

降级:
- 解析失败 → fallback:整段 raw 作为 revised_content
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
class ReviserAgent(BaseAgent):
    name = "ReviserAgent"
    version = "1.0.0"
    capabilities = ["content_revision", "issue_remediation"]
    memory_layers = ["semantic"]  # 修复成功率历史

    async def run(self, input: AgentInput) -> AgentOutput:
        content = input.book_settings.get("content", "") or ""
        issues = input.book_settings.get("issues", []) or []
        style_notes = input.book_settings.get("style_notes", "") or ""

        if not content:
            return AgentOutput(
                status="error",
                error="ReviserAgent: missing 'content'",
            )

        if not issues:
            # 无 issues 直接返原文
            return AgentOutput(
                status="ok",
                result={
                    "revised_content": content,
                    "changes_made": [],
                    "issues_addressed": 0,
                },
            )

        # 1. 渲染 prompt
        prompt = self.prompts.render(
            "reviser.j2",
            content=content,
            issues=issues,
            style_notes=style_notes,
        )

        # 2. 调 LLM
        try:
            response = await self.llm.chat(
                LLMChatRequest(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=8000,
                ),
                book_id=input.book_id,
                pipeline_run_id=input.pipeline_run_id,
                node_id=input.node_id,
                agent_id=self.name,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("ReviserAgent: LLM call failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"LLM call failed: {e}",
            )

        # 3. 解析 JSON;失败 fallback 到原始 content
        revised_content = response.content
        changes_made: list[str] = []
        try:
            data = json.loads(response.content)
            if isinstance(data, dict):
                revised_content = data.get("revised_content", revised_content)
                raw_changes = data.get("changes_made", []) or []
                if isinstance(raw_changes, list):
                    changes_made = [str(c) for c in raw_changes]
        except Exception as e:  # noqa: BLE001
            log.warning("ReviserAgent: JSON parse failed (%s), using raw content", e)

        return AgentOutput(
            status="ok",
            result={
                "revised_content": revised_content,
                "changes_made": changes_made,
                "issues_addressed": len(issues),
                "word_count": len(revised_content),
            },
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
