from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LLMCall(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    book_id: UUID | None = None
    pipeline_run_id: UUID | None = None
    task_id: UUID | None = None
    agent_id: str | None = None
    node_id: str | None = None
    provider: str
    model: str
    endpoint: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    cost_estimate: Decimal = Decimal("0")
    success: bool = True
    error_type: str | None = None
    trace_id: str | None = None
    created_at: datetime | None = None


class LLMChatRequest(BaseModel):
    model: str
    messages: list[dict]
    temperature: float = 0.7
    max_tokens: int = 0
    stream: bool = False
    idempotency_key: str | None = None


class LLMChatResponse(BaseModel):
    content: str
    model: str
    finish_reason: str
    usage: dict
    latency_ms: int
    cost_usd: Decimal
