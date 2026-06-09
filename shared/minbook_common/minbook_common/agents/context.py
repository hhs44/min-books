"""Pipeline context:跨 agent 节点传递数据。

PipelineContext 是一个 dataclass,挂在 pipeline-orchestrator / 单个服务进程内,
用于在 pipeline run 中跨节点传递 state(已执行的 node outputs / cancellation / trace)。
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class PipelineContext:
    pipeline_run_id: UUID
    book_id: UUID
    cancellation_event: asyncio.Event = field(default_factory=asyncio.Event)
    node_outputs: dict[str, Any] = field(default_factory=dict)  # node_id -> output
    trace_id: str | None = None

    def is_cancelled(self) -> bool:
        return self.cancellation_event.is_set()

    def set_node_output(self, node_id: str, output: Any) -> None:
        self.node_outputs[node_id] = output

    def get_node_output(self, node_id: str) -> Any:
        return self.node_outputs.get(node_id)
