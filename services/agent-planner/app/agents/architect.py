"""ArchitectAgent:建书时生成基础设定(详见 v2 §1.2)。

输入:book_settings(title/genre/language) + current_focus(作者意图)
输出:story_bible / style_guide / book_rules / character_matrix / length_governance
副作用:写 2 个真相文件(character_matrix + current_state)
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


class ArchitectOutput(BaseModel):
    """ArchitectAgent LLM 输出的结构化结果。"""

    story_bible: dict  # 世界观 / 设定
    style_guide: dict  # 文风指南
    book_rules: list[str]  # 硬规则
    character_matrix: dict  # 角色矩阵
    length_governance: dict  # 字数治理


@register_agent
class ArchitectAgent(BaseAgent):
    name = "ArchitectAgent"
    version = "1.0.0"
    capabilities = ["book_architecture", "story_bible_generation"]
    memory_layers = ["procedural"]  # 风格模板

    async def run(self, input: AgentInput) -> AgentOutput:
        prompt = self.prompts.render(
            "architect.j2",
            title=input.book_settings.get("title", ""),
            genre=input.book_settings.get("genre", ""),
            author_intent=input.current_focus,
            language=input.book_settings.get("language", "zh"),
        )

        request = LLMChatRequest(
            model="gpt-4o",  # 建书用强模型
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4000,
        )

        response = await self.llm.chat(
            request,
            book_id=input.book_id,
            pipeline_run_id=input.pipeline_run_id,
            node_id=input.node_id,
            agent_id=self.name,
        )

        # 解析 LLM 输出(JSON 格式)
        try:
            result = json.loads(response.content)
            architect_output = ArchitectOutput(**result)
        except Exception as e:  # noqa: BLE001
            log.exception("ArchitectAgent: LLM output parse failed")
            return AgentOutput(
                status="error",
                error=f"LLM output parse failed: {e}",
            )

        # 写 state-service(真相文件)
        # v3 plan 中提到要写 7 个真相 + 4 book_settings;
        # 此处实现核心 2 个(story_bible → current_state, character_matrix → character_matrix),
        # 其它真相文件可由后续 agent(Planner/Composer)在运行中初始化。
        try:
            await self.state.update_truth(
                input.book_id, "character_matrix", architect_output.character_matrix,
            )
            await self.state.update_truth(
                input.book_id, "current_state", architect_output.story_bible,
            )
        except Exception as e:  # noqa: BLE001
            # 写真相失败不阻断 agent(仅记录,book_id 可能尚未在 state 注册)
            log.warning("ArchitectAgent: state update failed: %s", e)

        return AgentOutput(
            status="ok",
            result=architect_output.model_dump(),
            metrics={
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            },
        )
