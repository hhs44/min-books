"""本服务内所有 agent 模块的注册表(用于启动时向 orchestrator 注册)。

用法:
```python
from minbook_common.agents.registry import register_agent

@register_agent
class MyAgent(BaseAgent):
    name = "MyAgent"
    ...
```
"""
from typing import Type

from .base import BaseAgent


class AgentRegistry:
    """进程内单例注册表(每个 agent 服务一个实例)。"""

    def __init__(self) -> None:
        self._agents: dict[str, Type[BaseAgent]] = {}

    def register(self, agent_class: Type[BaseAgent]) -> None:
        """注册一个 agent class(在 agent class 上用 @register 装饰)。"""
        if not issubclass(agent_class, BaseAgent):
            raise TypeError(f"{agent_class!r} is not a subclass of BaseAgent")
        if agent_class.name in self._agents:
            # 允许重复 import 时幂等
            return
        self._agents[agent_class.name] = agent_class

    def all(self) -> list[Type[BaseAgent]]:
        return list(self._agents.values())

    def get(self, name: str) -> Type[BaseAgent] | None:
        return self._agents.get(name)

    def names(self) -> list[str]:
        return list(self._agents.keys())


# 全局默认注册表(简单进程级单例,各服务也可自己 new AgentRegistry())
_global_registry = AgentRegistry()


def register_agent(cls: Type[BaseAgent]) -> Type[BaseAgent]:
    """装饰器:@register_agent — 注册到全局 + 返回原 class。"""
    _global_registry.register(cls)
    return cls


def get_global_registry() -> AgentRegistry:
    return _global_registry
