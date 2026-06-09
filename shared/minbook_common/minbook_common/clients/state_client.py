"""State Service 客户端(读写真相文件 + 创建 snapshot)。

通过 SignedHTTPClient 调 state-service /internal/state/* 端点。
"""
import os
from typing import Any
from uuid import UUID

from minbook_common.http_client import SignedHTTPClient


class StateClient:
    def __init__(self, service_name: str, base_url: str | None = None):
        self.service_name = service_name
        self.base_url = base_url or os.environ.get(
            "STATE_SERVICE_URL", "http://state-service:8007",
        )
        self._client: SignedHTTPClient | None = None

    def _get_client(self) -> SignedHTTPClient:
        if not self._client:
            self._client = SignedHTTPClient(self.service_name)
        return self._client

    async def get_truth(self, book_id: UUID, file_type: str) -> dict:
        r = await self._get_client().get(
            f"{self.base_url}/internal/state/{book_id}/truth/{file_type}",
        )
        r.raise_for_status()
        return r.json()

    async def update_truth(
        self,
        book_id: UUID,
        file_type: str,
        content: dict,
        expected_version: int | None = None,
    ) -> dict:
        r = await self._get_client().put(
            f"{self.base_url}/internal/state/{book_id}/truth/{file_type}",
            json={"content": content, "expected_version": expected_version},
        )
        r.raise_for_status()
        return r.json()

    async def create_snapshot(
        self,
        book_id: UUID,
        chapter_number: int | None,
        snapshot_json: dict[str, Any],
    ) -> dict:
        r = await self._get_client().post(
            f"{self.base_url}/internal/state/{book_id}/snapshot",
            json={
                "book_id": str(book_id),
                "chapter_number": chapter_number,
                "snapshot_json": snapshot_json,
            },
        )
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
