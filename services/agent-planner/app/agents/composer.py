"""ComposerAgent:从真相文件选上下文,编译规则栈(详见 v2 §1.2)。

**纯逻辑 agent,不调 LLM。** 选真相文件子集 + 编译规则栈,
输出 CompiledContext 给下游 WriterAgent。
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

log = logging.getLogger(__name__)


class CompiledContext(BaseModel):
    selected_truth_files: dict  # 选中的真相文件子集
    rule_stack: list[str]  # 规则栈(全规则按优先级)
    context_summary: str  # 上下文摘要(给 Writer)


@register_agent
class ComposerAgent(BaseAgent):
    name = "ComposerAgent"
    version = "1.0.0"
    capabilities = ["context_composition", "rule_stack_compilation"]
    memory_layers = []  # 纯逻辑 agent,无记忆层

    async def run(self, input: AgentInput) -> AgentOutput:
        chapter_intent = input.book_settings.get("chapter_intent", {})

        # 1. 选真相文件(只读需要的部分,不全量灌给 Writer)
        relevant_files = self._select_relevant_files(chapter_intent)

        # 2. 编译规则栈(从 book_rules + style_guide + chapter_intent)
        rule_stack = self._compile_rule_stack(input.book_settings, chapter_intent)

        # 3. 生成 context summary(给 Writer 的人读 hint)
        compiled = CompiledContext(
            selected_truth_files=relevant_files,
            rule_stack=rule_stack,
            context_summary=(
                f"chapter {chapter_intent.get('chapter_number', '?')} context: "
                f"{len(rule_stack)} rules, {len(relevant_files)} truth files"
            ),
        )

        return AgentOutput(status="ok", result=compiled.model_dump())

    def _select_relevant_files(self, chapter_intent: dict) -> dict:
        """选真相文件子集。

        简化版:返回全部 7 个真相文件的索引描述(包含 filter 提示),
        后续 Phase 可加 LLM 选择最相关的子集。
        """
        return {
            "current_state": {},
            "character_matrix": {
                "filter": "characters_involved",
                "characters": chapter_intent.get("characters_involved", []),
            },
            "pending_hooks": {},
            "chapter_summaries": {"filter": "recent_5_chapters"},
            "subplot_board": {},
            "emotional_arcs": {},
            "particle_ledger": {},
        }

    def _compile_rule_stack(
        self, book_settings: dict, chapter_intent: dict
    ) -> list[str]:
        """编译规则栈:硬规则 → 字数 → 文风 → 章节特定。"""
        rules: list[str] = []

        # 1. 硬规则
        rules.extend(book_settings.get("book_rules", []))

        # 2. 字数规则
        length_gov = book_settings.get("length_governance", {})
        if length_gov:
            target = length_gov.get("target_chapter_words", 3000)
            rules.append(f"target_chapter_words: {target}")
            min_w = length_gov.get("min_chapter_words", int(target * 0.85))
            max_w = length_gov.get("max_chapter_words", int(target * 1.15))
            rules.append(f"min_chapter_words: {min_w}")
            rules.append(f"max_chapter_words: {max_w}")

        # 3. 文风规则
        style = book_settings.get("style_guide", {})
        if style:
            rules.append(f"narrative_pov: {style.get('narrative_pov', 'third')}")
            rules.append(f"tense: {style.get('tense', 'past')}")
            if style.get("tone"):
                rules.append(f"tone: {style['tone']}")

        # 4. 章节特定规则
        if chapter_intent.get("style_notes"):
            rules.append(f"chapter_style: {chapter_intent['style_notes']}")
        if chapter_intent.get("emotional_arc"):
            rules.append(f"emotional_arc: {chapter_intent['emotional_arc']}")

        return rules
