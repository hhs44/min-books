"""FoundationReviewerAgent:审核 ArchitectAgent 的输出(详见 v2 §1.2)。

审核维度:
- story_bible 内部一致性
- character_matrix 是否有冲突
- book_rules 是否清晰可执行
- style_guide 和 genre 是否匹配

返回 FoundationReview(verdict / issues / overall_score)。
temperature=0.3,审核要稳定。
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


class FoundationIssue(BaseModel):
    severity: str  # critical | major | minor
    type: str  # consistency | clarity | completeness | style
    description: str
    suggestion: str


class FoundationReview(BaseModel):
    verdict: str  # PASS | FAIL
    issues: list[FoundationIssue]
    overall_score: float  # 0-1


@register_agent
class FoundationReviewerAgent(BaseAgent):
    name = "FoundationReviewerAgent"
    version = "1.0.0"
    capabilities = ["foundation_review"]
    memory_layers = []  # 审核无记忆

    async def run(self, input: AgentInput) -> AgentOutput:
        # 输入:book_settings.architect_output
        architect_output = input.book_settings.get("architect_output", {})

        if not architect_output:
            return AgentOutput(
                status="error",
                error="Missing 'architect_output' in book_settings",
            )

        prompt = self.prompts.render(
            "foundation_reviewer.j2",
            architect_output=architect_output,
        )

        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 审核要稳定
                max_tokens=2000,
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            agent_id=self.name,
        )

        try:
            review = FoundationReview(**json.loads(response.content))
        except Exception as e:  # noqa: BLE001
            log.exception("FoundationReviewerAgent: parse failed")
            return AgentOutput(status="error", error=f"Parse failed: {e}")

        return AgentOutput(
            status="ok",
            result=review.model_dump(),
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
