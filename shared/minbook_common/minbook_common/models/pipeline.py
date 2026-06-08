from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PipelineNode(BaseModel):
    id: str
    agent_ref: str | None = None
    function: str | None = None
    type: str = "agent"  # agent | function | condition
    inputs_from: list[str] = Field(default_factory=list)
    condition: str | None = None
    parallel_group: str | None = None
    streaming: bool = False


class PipelineDefinition(BaseModel):
    id: str
    description: str = ""
    version: int = 1
    nodes: list[PipelineNode]
    edges: list[dict] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class PipelineRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    pipeline_id: str
    book_id: UUID
    status: str = "pending"
    # pending | running | cancelling | cancelled | completed | failed | in_dlq
    dag_definition: dict
    checkpoints: dict = Field(default_factory=dict)
    error: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
