from pydantic import BaseModel, Field


class AgentCard(BaseModel):
    """v2 spec §4.1 Agent Card schema,服务启动时注册到 orchestrator。"""

    agent_id: str
    service: str
    name: str
    version: str
    capabilities: list[str]
    inputs: dict
    outputs: dict
    memory_layers: list[str] = Field(default_factory=list)
    can_call: list[str] = Field(default_factory=list)
    sla: dict = Field(default_factory=dict)
    supported_languages: list[str] = Field(default_factory=lambda: ["zh"])


class AgentRegistrationRequest(BaseModel):
    card: AgentCard
    endpoint: str  # 例: "http://agent-writer-service:8004"
