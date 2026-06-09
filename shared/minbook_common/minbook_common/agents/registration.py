"""向 orchestrator 注册 agent cards + 持续心跳(详见 v2 §4.3)。

每个 agent 服务启动时:
1. register_all():把本服务所有 agent 的 AgentCard POST 给 orchestrator
2. heartbeat_loop():每 N 秒 POST 一次心跳(orchestrator 据此知道服务存活)

orchestrator 还没实现(v4 才有),所有调用都 try/except,失败只记 log 不 crash。
"""
import asyncio
import logging
import os
from typing import Type

from minbook_common.http_client import SignedHTTPClient
from minbook_common.agents.base import BaseAgent
from minbook_common.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


class AgentRegistrar:
    def __init__(
        self,
        service_name: str,
        service_endpoint: str,
        orchestrator_url: str | None = None,
        heartbeat_interval: int = 30,
    ):
        self.service_name = service_name
        self.service_endpoint = service_endpoint
        self.orchestrator_url = orchestrator_url or os.environ.get(
            "PIPELINE_ORCHESTRATOR_URL", "http://pipeline-orchestrator:8002",
        )
        self.heartbeat_interval = heartbeat_interval
        self._client: SignedHTTPClient | None = None
        self._task: asyncio.Task | None = None

    def _get_client(self) -> SignedHTTPClient:
        if not self._client:
            self._client = SignedHTTPClient(self.service_name)
        return self._client

    async def register_all(self, registry: AgentRegistry) -> None:
        """注册本服务所有 agent。"""
        for agent_class in registry.all():
            # endpoint 在 invoke 时才有意义;register/heartbeat 阶段只传 service。
            card = agent_class.to_card(self.service_name)
            try:
                r = await self._get_client().post(
                    f"{self.orchestrator_url}/internal/orchestrator/agents/register",
                    json={
                        "card": card.model_dump(mode="json"),
                        "endpoint": self.service_endpoint,
                    },
                    timeout=10.0,
                )
                r.raise_for_status()
                logger.info("Registered agent %s", card.agent_id)
            except Exception as e:
                # v3 plan 阶段 orchestrator 不存在,只记 log 不 crash
                logger.info(
                    "Skipping register %s (orchestrator unavailable): %s",
                    card.agent_id, e,
                )

    async def heartbeat_loop(self, registry: AgentRegistry) -> None:
        """持续心跳(每 N 秒)。"""
        while True:
            try:
                for agent_class in registry.all():
                    # 心跳只关心 service + agent_id + version;不传 endpoint。
                    card = agent_class.to_card(self.service_name)
                    r = await self._get_client().post(
                        f"{self.orchestrator_url}/internal/orchestrator/agents/{card.agent_id}/heartbeat",
                        timeout=5.0,
                    )
                    r.raise_for_status()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Heartbeat skipped (orchestrator unavailable): %s", e)
            await asyncio.sleep(self.heartbeat_interval)

    def start(self, registry: AgentRegistry) -> None:
        """启动后台注册 + 心跳。"""

        async def _runner() -> None:
            try:
                await self.register_all(registry)
            except Exception as e:
                logger.warning("register_all failed: %s", e)
            try:
                await self.heartbeat_loop(registry)
            except asyncio.CancelledError:
                logger.info("heartbeat loop cancelled")
                raise

        self._task = asyncio.create_task(_runner())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
