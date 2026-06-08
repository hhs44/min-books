from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MinBookEvent(BaseModel):
    """所有 NATS 事件的统一包装,详见 v2 spec §3.2.4。"""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    source_service: str
    source_version: str
    trace_id: str | None = None
    span_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
