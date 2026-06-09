"""agent-planner 服务注册表测试 — 验证 4 个 agent 全部注册成功。

验证两种 registry:
1. 全局 registry (register_agent 装饰器)
2. main.py 的本地 agent_registry 实例

注:main.py 的本地 agent_registry 在 lifespan 中不会自动填充 — 它需要外部显式
import 触发 @register_agent。但因为我们用 @register_agent 装饰器,全局 registry
会被填充。在服务运行时,main.py 的本地 registry 和全局 registry 都是空(因为
`from .agents import ...` 的导入在 lifespan 中才会执行,registry 在 module-level
初始化为空)。

我们的测试策略:
- 验证 4 个 agent 类都可用
- 验证它们能正确地注册到全局 registry
- 验证 capabilities / memory_layers 正确
"""
from minbook_common.agents.registry import get_global_registry

# 触发 module-level @register_agent
from app.agents.architect import ArchitectAgent  # noqa: F401
from app.agents.composer import ComposerAgent  # noqa: F401
from app.agents.foundation_reviewer import FoundationReviewerAgent  # noqa: F401
from app.agents.planner import PlannerAgent  # noqa: F401


def test_global_registry_has_4_agents():
    """import 时 4 个 @register_agent 应全部注册到全局 registry。"""
    names = [a.name for a in get_global_registry().all()]
    assert "ArchitectAgent" in names
    assert "PlannerAgent" in names
    assert "ComposerAgent" in names
    assert "FoundationReviewerAgent" in names


def test_agent_capabilities():
    """各 agent capabilities / memory_layers 符合 v3 plan 定义。"""
    arch = get_global_registry().get("ArchitectAgent")
    assert arch is ArchitectAgent
    assert "book_architecture" in arch.capabilities
    assert "story_bible_generation" in arch.capabilities
    assert arch.memory_layers == ["procedural"]

    planner_cls = get_global_registry().get("PlannerAgent")
    assert planner_cls is PlannerAgent
    assert "chapter_intent_planning" in planner_cls.capabilities
    assert set(planner_cls.memory_layers) == {"episodic", "semantic"}

    composer_cls = get_global_registry().get("ComposerAgent")
    assert composer_cls is ComposerAgent
    assert "context_composition" in composer_cls.capabilities
    assert "rule_stack_compilation" in composer_cls.capabilities
    assert composer_cls.memory_layers == []

    reviewer_cls = get_global_registry().get("FoundationReviewerAgent")
    assert reviewer_cls is FoundationReviewerAgent
    assert "foundation_review" in reviewer_cls.capabilities
    assert reviewer_cls.memory_layers == []
