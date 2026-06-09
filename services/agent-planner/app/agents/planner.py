"""PlannerAgent:从作者意图 + 焦点 → 章节意图(详见 v2 §1.2)。

流程:
1. recall 历史章节意图(episodic,vector recall)
2. load_procedural(planner preferences)
3. 读真相(current_state + character_matrix)
4. 渲染 prompts/planner.j2
5. 调 LLM(模型 gpt-4o, max_tokens=2000)
6. JSON 解析 → ChapterIntent
7. store_episode(为未来 recall)
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


class ChapterIntent(BaseModel):
    chapter_number: int
    title: str
    intent: str  # 章节目标(中文 1-2 句)
    key_events: list[str]  # 关键事件清单
    characters_involved: list[str]  # 出场角色
    emotional_arc: str  # 情绪走向
    style_notes: str  # 风格提示


@register_agent
class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    version = "1.0.0"
    capabilities = ["chapter_intent_planning"]
    memory_layers = ["episodic", "semantic"]  # 历史章节意图 + 作者偏好

    async def run(self, input: AgentInput) -> AgentOutput:
        # 1. Recall 上下文:历史章节 + 作者偏好
        try:
            past_intents = await self.recall_context(
                book_id=input.book_id,
                query=f"chapters similar to: {input.current_focus}",
                top_k=5,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("PlannerAgent: recall_context failed: %s", e)
            past_intents = []

        try:
            preferences = await self.load_procedural("planner.preferences") or ""
        except Exception as e:  # noqa: BLE001
            log.warning("PlannerAgent: load_procedural failed: %s", e)
            preferences = ""

        # 2. 读真相(当前状态)
        current_state: dict = {}
        character_matrix: dict = {}
        try:
            current_state = await self.state.get_truth(input.book_id, "current_state")
        except Exception as e:  # noqa: BLE001
            log.warning("PlannerAgent: get_truth(current_state) failed: %s", e)
        try:
            character_matrix = await self.state.get_truth(input.book_id, "character_matrix")
        except Exception as e:  # noqa: BLE001
            log.warning("PlannerAgent: get_truth(character_matrix) failed: %s", e)

        # 3. 渲染 prompt
        prompt = self.prompts.render(
            "planner.j2",
            current_focus=input.current_focus,
            book_settings=input.book_settings,
            current_state=current_state,
            character_matrix=character_matrix,
            past_intents=past_intents,
            preferences=preferences,
        )

        # 4. 调 LLM
        response = await self.llm.chat(
            LLMChatRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            ),
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            node_id=input.node_id,
            agent_id=self.name,
        )

        # 5. 解析输出
        try:
            result = json.loads(response.content)
            intent = ChapterIntent(**result)
        except Exception as e:  # noqa: BLE001
            log.exception("PlannerAgent: parse failed")
            return AgentOutput(status="error", error=f"Parse failed: {e}")

        # 6. Store episode(为未来 recall)
        try:
            await self.store_episode(
                book_id=input.book_id,
                episode={
                    "chapter_number": intent.chapter_number,
                    "title": intent.title,
                    "intent": intent.intent,
                    "key_events": intent.key_events,
                },
            )
        except Exception as e:  # noqa: BLE001
            # store_episode 失败不阻断(降级)
            log.warning("PlannerAgent: store_episode failed: %s", e)

        return AgentOutput(
            status="ok",
            result=intent.model_dump(),
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
