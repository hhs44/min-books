"""ObserverAgent:从章节正文提取事实,生成 JSON delta(详见 v2 §1.2)。

输入:章节内容
输出:delta(结构化事实,待 SettlerAgent 写入 7 个真相文件)

delta 形如:
{
  "current_state": {"chapter_progress": 5, "last_event": "..."},
  "character_matrix": {"updates": [{"name": "X", "status_change": "..."}]},
  "pending_hooks": {"new_hooks": [...], "resolved": [...]},
  ...
}
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


# delta 可影响的真相文件类型
DELTA_TARGETS = [
    "current_state",
    "character_matrix",
    "pending_hooks",
    "chapter_summaries",
    "subplot_board",
    "emotional_arcs",
    "particle_ledger",
]


@register_agent
class ObserverAgent(BaseAgent):
    name = "ObserverAgent"
    version = "1.0.0"
    capabilities = ["fact_extraction", "truth_delta_generation"]
    memory_layers = []  # 每次 fresh 跑

    async def run(self, input: AgentInput) -> AgentOutput:
        content = input.book_settings.get("content", "") or ""
        chapter_number = input.book_settings.get("chapter_number")

        if not content:
            return AgentOutput(
                status="error",
                error="ObserverAgent: missing 'content'",
            )

        # 1. 渲染 prompt
        prompt = self.prompts.render(
            "observer.j2",
            content=content,
            chapter_number=chapter_number,
            delta_targets=DELTA_TARGETS,
        )

        # 2. 调 LLM
        try:
            response = await self.llm.chat(
                LLMChatRequest(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=4000,
                ),
                book_id=input.book_id,
                pipeline_run_id=input.pipeline_run_id,
                node_id=input.node_id,
                agent_id=self.name,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("ObserverAgent: LLM call failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"LLM call failed: {e}",
            )

        # 3. 解析 JSON delta
        try:
            delta = json.loads(response.content)
        except Exception as e:  # noqa: BLE001
            log.warning("ObserverAgent: JSON parse failed: %s", e)
            return AgentOutput(
                status="error",
                error=f"Parse failed: {e}",
                result={"raw_content": response.content[:500]},
            )

        # 4. 校验 delta 形如 dict;过滤出允许的 key
        if not isinstance(delta, dict):
            return AgentOutput(
                status="error",
                error="ObserverAgent: delta must be a dict",
            )

        # 收集受影响真相文件
        affected = [k for k in delta.keys() if k in DELTA_TARGETS]
        unknown = [k for k in delta.keys() if k not in DELTA_TARGETS]

        if unknown:
            log.warning("ObserverAgent: ignored unknown delta keys: %s", unknown)

        return AgentOutput(
            status="ok",
            result={
                "delta": {k: delta[k] for k in affected},
                "affected_files": affected,
                "ignored_keys": unknown,
                "chapter_number": chapter_number,
            },
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
