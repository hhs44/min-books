"""AIGCDetector + SensitiveWordsDetector 单元测试(纯规则)。"""
from uuid import uuid4

import pytest

from app.agents.aigc_detector import AIGCDetector
from app.agents.sensitive_words import SensitiveWordsDetector
from minbook_common.agents.base import AgentInput


# ---------- AIGCDetector ----------

@pytest.mark.asyncio
async def test_aigc_detector_flags_ai_cliches():
    """含典型 AI 套话 → is_aigc=True。"""
    book_id = uuid4()
    agent = AIGCDetector(None, None, None, None)

    # 充分长度,触发多个 AI 模式 + 句长方差异常
    content = (
        "首先,我们来看一下这个问题。其次,这非常重要。"
        "此外,这需要深入探讨。"
        "然而,我们也要注意其他方面。"
        "因此,有必要进行系统分析。"
        "综上所述,这个主题值得关注。"
        "总而言之,希望本文能对你有所帮助。"
        "作为一个AI语言模型,让我来帮您分析。"
        "值得注意的是,这种现象在当代社会中普遍存在。"
    )

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": content},
        )
    )

    assert output.status == "ok", output.error
    assert output.result["is_aigc"] is True
    assert output.result["confidence"] >= 0.3
    matched_names = {s["signal"] for s in output.result["signals"] if s.get("matched")}
    # 不依赖具体哪个 signal,只要至少一个典型 AI 模式命中
    assert any(
        name in matched_names
        for name in (
            "self_reference_as_ai",
            "phrase_hope_helps",
            "phrase_in_conclusion",
            "phrase_in_summary",
        )
    )


@pytest.mark.asyncio
async def test_aigc_detector_human_text_passes():
    """自然中文小说文本 → confidence 较低。"""
    book_id = uuid4()
    agent = AIGCDetector(None, None, None, None)

    # 多样化句长、不同段落长度
    content = (
        "雨下得很大,Alice 站在门口,雨水顺着屋檐滴落。\n\n"
        "她看着远方的山,心里有些不安。\n\n"
        "远处的灯塔亮着微弱的光,像是在指引她什么。\n\n"
        "她突然想到了什么,转身跑进屋里。"
    )

    output = await agent.run(
        AgentInput(book_id=book_id, book_settings={"content": content}),
    )

    assert output.status == "ok"
    # 人类文本不应被强标记为 AIGC
    # 但某些 heuristic 可能仍触发,只断言 confidence < 0.7
    assert output.result["confidence"] < 0.7


# ---------- SensitiveWordsDetector ----------

@pytest.mark.asyncio
async def test_sensitive_words_detector_finds_violence():
    """含暴力词 → flagged=True,found 非空。"""
    book_id = uuid4()
    agent = SensitiveWordsDetector(None, None, None, None)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "战斗场面非常血腥,双方都很残忍。"},
        )
    )

    assert output.status == "ok", output.error
    assert output.result["flagged"] is True
    assert output.result["total_matches"] >= 2
    categories = output.result["categories"]
    assert "violence" in categories
    assert categories["violence"] >= 2


@pytest.mark.asyncio
async def test_sensitive_words_detector_pii_pattern():
    """含手机号 PII → pii 类别被命中。"""
    book_id = uuid4()
    agent = SensitiveWordsDetector(None, None, None, None)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "联系方式:13800138000,请联系。"},
        )
    )

    assert output.status == "ok"
    assert output.result["flagged"] is True
    assert "pii" in output.result["categories"]


@pytest.mark.asyncio
async def test_sensitive_words_detector_clean_text():
    """干净文本 → flagged=False。"""
    book_id = uuid4()
    agent = SensitiveWordsDetector(None, None, None, None)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "Alice 走进花园,看着盛开的玫瑰。"},
        )
    )

    assert output.status == "ok"
    assert output.result["flagged"] is False
    assert output.result["total_matches"] == 0
