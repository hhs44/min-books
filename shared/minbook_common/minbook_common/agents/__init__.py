"""MinBook 共享 agent 基础设施。

- base:    BaseAgent 抽象基类 + AgentInput / AgentOutput Pydantic
- context: PipelineContext dataclass
- registry: AgentRegistry + @register_agent 装饰器
- prompt_loader: Jinja2 prompt 模板加载器
- registration:  AgentRegistrar(向 orchestrator 注册 + 心跳)
"""
from .base import AgentInput, AgentOutput, BaseAgent
from .context import PipelineContext
from .registry import AgentRegistry, register_agent

__all__ = [
    "AgentInput",
    "AgentOutput",
    "BaseAgent",
    "PipelineContext",
    "AgentRegistry",
    "register_agent",
]
