"""注册表测试:9 个 agent 都通过 @register_agent 注册到全局 registry。"""
import pytest


@pytest.mark.asyncio
async def test_all_nine_agents_registered():
    """导入 9 个 agent 模块后,global registry 应至少包含 9 个名字。"""
    from minbook_common.agents.registry import get_global_registry

    # 主动导入(模拟 main.py 启动)
    from app.agents import (  # noqa: F401
        aigc_detector,
        continuity_auditor,
        observer,
        post_write_validator,
        radar,
        reviser,
        sensitive_words,
        settler,
        state_validator,
    )

    reg = get_global_registry()
    names = set(reg.names())
    expected = {
        "ContinuityAuditor",
        "ReviserAgent",
        "StateValidator",
        "PostWriteValidator",
        "ObserverAgent",
        "SettlerAgent",
        "AIGCDetector",
        "SensitiveWordsDetector",
        "RadarAgent",
    }
    missing = expected - names
    assert not missing, f"missing agents: {missing}, have: {sorted(names)}"
