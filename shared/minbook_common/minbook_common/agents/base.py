"""BaseAgent:所有 agent 的抽象基类。

设计要点(v3 plan §Phase A Task 1):
- AgentInput / AgentOutput 是 Pydantic v2 model,各 agent 子类可扩展。
- BaseAgent 是 ABC,子类必须实现 `async def run(...)`。
- 提供 4 个 helper:recall_context / store_episode / load_procedural / to_card。
- 4 个 client 依赖(llm / state / memory / prompts)在 __init__ 注入。
"""
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from minbook_common.models import AgentCard


class AgentInput(BaseModel):
    """agent 输入基类(各 agent 子类化扩展)。"""

    book_id: UUID
    book_settings: dict = {}
    current_focus: str = ""
    pipeline_run_id: UUID | None = None
    node_id: str | None = None
    idempotency_key: str | None = None


class AgentOutput(BaseModel):
    """agent 输出基类。"""

    status: str = "ok"  # ok | error | warning
    result: Any = None
    error: str | None = None
    metrics: dict = {}  # tokens, cost, latency


class BaseAgent(ABC):
    """所有 agent 继承这个类。"""

    # 子类必须定义(可被 @register_agent 装饰器自动读取)
    name: str = "base"
    version: str = "0.1.0"
    capabilities: list[str] = []
    memory_layers: list[str] = []  # episodic | semantic | procedural

    def __init__(self, llm_client, state_client, memory_client, prompt_loader):
        self.llm = llm_client
        self.state = state_client
        self.memory = memory_client
        self.prompts = prompt_loader

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        """主入口(子类实现)。"""
        raise NotImplementedError

    async def recall_context(
        self, book_id: UUID, query: str, top_k: int = 5
    ) -> list[dict]:
        """从本 agent 私有记忆 recall 上下文。"""
        return await self.memory.recall(
            book_id=book_id, query=query, top_k=top_k,
        )

    async def store_episode(
        self,
        book_id: UUID,
        episode: dict,
        embedding: list[float] | None = None,
    ) -> str:
        """存储 episodic 记忆(详见 v2 §2.4)。"""
        return await self.memory.store_episode(
            book_id=book_id, episode=episode, embedding=embedding,
        )

    async def load_procedural(self, template_name: str) -> str | None:
        """加载程序性记忆(prompt 模板)。"""
        return await self.memory.load_procedural(template_name)

    def to_card(self, service: str, endpoint: str) -> AgentCard:
        """生成本 agent 的 AgentCard(用于向 orchestrator 注册)。"""
        return AgentCard(
            agent_id=f"{service}.{self.name}.{self.version}",
            service=service,
            name=self.name,
            version=self.version,
            capabilities=list(self.capabilities),
            inputs={},  # 子类可覆盖
            outputs={},
            memory_layers=list(self.memory_layers),
            can_call=["llm-gateway", "state-service"],
            sla={"p95_latency_ms": 30000, "max_concurrent": 3},
        )
