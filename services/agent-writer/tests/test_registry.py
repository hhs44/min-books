"""注册表测试:7 个 agent 都通过 @register_agent 注册到全局 registry。"""
import pytest


@pytest.mark.asyncio
async def test_all_seven_agents_registered():
    """导入 7 个 agent 模块后,global registry 应至少包含 7 个名字。"""
    from minbook_common.agents.registry import get_global_registry

    # 主动导入(模拟 main.py 启动)
    from app.agents import (  # noqa: F401
        chapter_analyzer,
        consolidator,
        length_normalizer,
        polisher,
        short_fiction_writer,
        style_analyzer,
        writer,
    )

    reg = get_global_registry()
    names = set(reg.names())
    expected = {
        "WriterAgent",
        "PolisherAgent",
        "LengthNormalizer",
        "ConsolidatorAgent",
        "ChapterAnalyzerAgent",
        "StyleAnalyzer",
        "ShortFictionWriterAgent",
    }
    missing = expected - names
    assert not missing, f"missing agents: {missing}, have: {sorted(names)}"
