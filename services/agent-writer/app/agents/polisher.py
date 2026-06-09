"""PolisherAgent:对 draft_content 做润色(不改情节,只优化表达,详见 v2 §1.2)。

调 LLM(gpt-4o, temp=0.5, max=8000),期望返 JSON:
  {"polished_content": "<全文>", "changes_made": ["...", ...]}

JSON 解析失败时 fallback:整段当作 polished_content,changes_made=[]。
"""
from __future__ import annotations

import json
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


class PolisherInput(AgentInput):
    draft_content: str = ""
    style_notes: str = ""


class PolisherOutput(BaseModel):
    polished_content: str
    changes_made: list[str]


@register_agent
class PolisherAgent(BaseAgent):
    name = "PolisherAgent"
    version = "1.0.0"
    capabilities = ["text_polishing"]
    memory_layers = ["semantic"]  # 风格偏好

    async def run(self, input: AgentInput) -> AgentOutput:
        draft_content = (
            getattr(input, "draft_content", "")
            or input.book_settings.get("draft_content", "")
        )
        style_notes = (
            getattr(input, "style_notes", "")
            or input.book_settings.get("style_notes", "")
        )

        if not draft_content:
            return AgentOutput(
                status="error",
                error="PolisherAgent: missing 'draft_content'",
            )

        prompt = self.prompts.render(
            "polisher.j2",
            draft_content=draft_content,
            style_notes=style_notes,
        )

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

        # 解析 JSON;失败 fallback 到原始 content
        try:
            data = json.loads(response.content)
            output = PolisherOutput(**data)
        except Exception as e:  # noqa: BLE001
            log.warning("PolisherAgent: JSON parse failed, falling back. err=%s", e)
            output = PolisherOutput(
                polished_content=response.content,
                changes_made=[],
            )

        return AgentOutput(
            status="ok",
            result=output.model_dump(),
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
