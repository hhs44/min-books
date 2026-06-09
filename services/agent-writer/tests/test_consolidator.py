"""ConsolidatorAgent 单元测试 — 纯逻辑,不调 LLM。"""
from uuid import uuid4

import pytest

from app.agents.consolidator import ConsolidatorAgent
from minbook_common.agents.base import AgentInput


def _make_agent() -> ConsolidatorAgent:
    from minbook_common.agents.prompt_loader import PromptLoader

    return ConsolidatorAgent(
        llm_client=None, state_client=None, memory_client=None,
        prompt_loader=PromptLoader(template_dir="prompts"),
    )


@pytest.mark.asyncio
async def test_consolidator_merges_string_chapters():
    agent = _make_agent()
    output = await agent.run(
        AgentInput(
            book_id=uuid4(),
            book_settings={"chapters": ["第一章正文。", "第二章正文。", "第三章正文。"]},
        )
    )

    assert output.status == "ok"
    assert output.result["total_chapters"] == 3
    assert "第一章正文。" in output.result["merged"]
    assert "第二章正文。" in output.result["merged"]
    assert "第三章正文。" in output.result["merged"]
    assert "---" in output.result["merged"]  # 默认分隔符


@pytest.mark.asyncio
async def test_consolidator_handles_dict_chapters_with_titles():
    """章节传 dict 且 include_titles=True → 应输出标题。"""
    agent = _make_agent()
    output = await agent.run(
        AgentInput(
            book_id=uuid4(),
            book_settings={
                "chapters": [
                    {"title": "序章", "content": "序章内容"},
                    {"title": "第二章", "content": "第二章内容"},
                ],
                "include_titles": True,
                "separator": "\n\n",
            },
        )
    )

    assert output.status == "ok"
    assert output.result["total_chapters"] == 2
    assert "# 序章" in output.result["merged"]
    assert "# 第二章" in output.result["merged"]


@pytest.mark.asyncio
async def test_consolidator_empty():
    agent = _make_agent()
    output = await agent.run(AgentInput(book_id=uuid4(), book_settings={}))
    assert output.status == "ok"
    assert output.result["merged"] == ""
    assert output.result["total_chapters"] == 0
