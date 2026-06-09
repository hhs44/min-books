"""LLM Gateway HTTP 客户端(带 trace / 幂等键 / cost 上报)。

通过 SignedHTTPClient 自动带 HMAC 签名,headers 透传 trace context 给 llm-gateway。
"""
import os
from uuid import UUID

from minbook_common.http_client import SignedHTTPClient
from minbook_common.models import LLMChatRequest, LLMChatResponse


class LLMClient:
    def __init__(self, service_name: str, base_url: str | None = None):
        self.service_name = service_name
        self.base_url = base_url or os.environ.get(
            "LLM_GATEWAY_URL", "http://llm-gateway:8006",
        )
        self._client: SignedHTTPClient | None = None

    def _get_client(self) -> SignedHTTPClient:
        if not self._client:
            self._client = SignedHTTPClient(self.service_name)
        return self._client

    async def chat(
        self,
        request: LLMChatRequest,
        book_id: UUID | None = None,
        pipeline_run_id: UUID | None = None,
        task_id: UUID | None = None,
        node_id: str | None = None,
        agent_id: str | None = None,
        trace_id: str | None = None,
    ) -> LLMChatResponse:
        """调 LLM Gateway。自动带 trace + 幂等键。"""
        client = self._get_client()
        headers: dict[str, str] = {}
        if book_id:
            headers["X-Book-Id"] = str(book_id)
        if pipeline_run_id:
            headers["X-Pipeline-Run-Id"] = str(pipeline_run_id)
        if task_id:
            headers["X-Task-Id"] = str(task_id)
        if node_id:
            headers["X-Node-Id"] = node_id
        if agent_id:
            headers["X-Agent-Id"] = agent_id
        if trace_id:
            # 用 trace_id 作为幂等键(同一 trace 复用)
            headers["Idempotency-Key"] = trace_id

        r = await client.post(
            f"{self.base_url}/internal/llm/chat",
            json=request.model_dump(mode="json"),
            headers=headers,
            timeout=300.0,
        )
        r.raise_for_status()
        return LLMChatResponse(**r.json())

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
