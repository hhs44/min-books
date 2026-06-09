"""PostWriteValidator 单元测试(纯逻辑)。"""
from uuid import uuid4

import pytest

from app.agents.post_write_validator import PostWriteValidator
from minbook_common.agents.base import AgentInput


@pytest.mark.asyncio
async def test_post_write_validator_spot_fixes_chinese_punctuation():
    """中文字符间的空格+半角逗号 → 应被 spot-fix 为全角逗号。"""
    book_id = uuid4()
    agent = PostWriteValidator(None, None, None, None)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "content": "Alice 走向城堡 , 她看到了 Bob 。他们一起前行",
            },
        )
    )

    assert output.status == "ok"
    assert output.result["valid"] is True
    # 应该有 1+ 个 spot_fix
    assert output.result["spot_fix_count"] >= 1
    # fixed_content 应该是修复后的版本
    assert "，" in output.result["fixed_content"]


@pytest.mark.asyncio
async def test_post_write_validator_detects_cross_chapter_duplicates():
    """历史片段与当前章节有 8-gram 重复 → duplicates 列表非空。"""
    book_id = uuid4()
    agent = PostWriteValidator(None, None, None, None)

    # 共 8 字符片段
    shared = "Alice走入了古老城堡大门"
    history = [f"前面是 {shared} ,Bob 跟随其后"]

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "content": f"在第三章,{shared},迎接她的命运。",
                "history_excerpts": history,
            },
        )
    )

    assert output.status == "ok"
    # 至少应有 1 个 duplicate cluster
    assert output.result["duplicate_count"] >= 1
    # issues 列表有 cross_chapter_duplicate
    assert any(
        i.get("check") == "cross_chapter_duplicate"
        for i in output.result["issues"]
    )


@pytest.mark.asyncio
async def test_post_write_validator_empty_content_is_critical():
    """空内容 → critical issue,valid=False。"""
    book_id = uuid4()
    agent = PostWriteValidator(None, None, None, None)

    output = await agent.run(
        AgentInput(book_id=book_id, book_settings={"content": "   "}),
    )

    assert output.status == "warning"
    assert output.result["valid"] is False
    assert any(
        i.get("severity") == "critical" for i in output.result["issues"]
    )
