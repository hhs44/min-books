"""ComposerAgent 单元测试 — 纯逻辑 agent,不调 LLM。"""
from uuid import uuid4

import pytest

from app.agents.composer import ComposerAgent
from minbook_common.agents.base import AgentInput


def _make_agent() -> ComposerAgent:
    """Composer 不调 LLM/state/memory,只需要 PromptLoader(但也不真用 prompt)。"""
    from minbook_common.agents.prompt_loader import PromptLoader

    return ComposerAgent(
        llm_client=None,  # Composer 不调 LLM
        state_client=None,  # Composer 不调 state
        memory_client=None,  # Composer 不调 memory
        prompt_loader=PromptLoader(template_dir="prompts"),
    )


@pytest.mark.asyncio
async def test_composer_compiles_rule_stack():
    """Composer 是纯逻辑 agent:编译 book_rules + 字数 + 文风 + 章节特定 → rule_stack。"""
    agent = _make_agent()

    output = await agent.run(
        AgentInput(
            book_id=uuid4(),
            book_settings={
                "book_rules": ["no anachronism", "consistent character voice"],
                "length_governance": {
                    "target_chapter_words": 3000,
                    "min_chapter_words": 2500,
                    "max_chapter_words": 3500,
                },
                "style_guide": {"narrative_pov": "first", "tense": "past", "tone": "warm"},
                "chapter_intent": {
                    "chapter_number": 5,
                    "style_notes": "action-packed",
                    "emotional_arc": "rising tension",
                },
            },
        )
    )

    assert output.status == "ok"
    rules = output.result["rule_stack"]
    # 硬规则
    assert "no anachronism" in rules
    assert "consistent character voice" in rules
    # 字数规则
    assert "target_chapter_words: 3000" in rules
    assert "min_chapter_words: 2500" in rules
    assert "max_chapter_words: 3500" in rules
    # 文风规则
    assert "narrative_pov: first" in rules
    assert "tense: past" in rules
    assert "tone: warm" in rules
    # 章节特定
    assert "chapter_style: action-packed" in rules
    assert "emotional_arc: rising tension" in rules

    # context_summary
    assert "chapter 5" in output.result["context_summary"]
    # selected_truth_files: 7 个真相文件索引
    selected = output.result["selected_truth_files"]
    assert "current_state" in selected
    assert "character_matrix" in selected
    assert "pending_hooks" in selected
    assert "chapter_summaries" in selected
    assert "subplot_board" in selected
    assert "emotional_arcs" in selected
    assert "particle_ledger" in selected


@pytest.mark.asyncio
async def test_composer_no_llm_call():
    """Composer 不调 LLM,空 book_settings 不报错。"""
    agent = _make_agent()
    output = await agent.run(AgentInput(book_id=uuid4(), book_settings={}))
    assert output.status == "ok"
    assert output.result["rule_stack"] == []
    assert len(output.result["selected_truth_files"]) == 7
