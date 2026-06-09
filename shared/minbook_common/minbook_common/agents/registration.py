"""向 orchestrator 注册 agent cards + 持续心跳(详见 v2 §4.3 + v6 修复)。

每个 agent 服务启动时:
1. register_all_with_retry():把本服务所有 agent 的 AgentCard POST 给 orchestrator
   失败 retry(指数退避,最多 5 次)后落 logger.warning,不阻塞 lifespan
2. heartbeat_loop():每 N 秒 POST 一次心跳(orchestrator 据此知道服务存活)

v6 修复: 旧版只 try/except 一次就 log.info("Skipping"),但 orchestrator 启动顺序可能
晚于 agent(例如 docker compose 重启),导致首次 register 拿 503/404 就一蹶不振。
现在显式重试 + 启动时阻塞式重试直到首次成功或重试用尽(其它失败用 warning 记)。
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
        max_register_retries: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 10.0,
    ):
        self.service_name = service_name
        self.service_endpoint = service_endpoint
        self.orchestrator_url = orchestrator_url or os.environ.get(
            "PIPELINE_ORCHESTRATOR_URL", "http://pipeline-orchestrator:8002",
        )
        self.heartbeat_interval = heartbeat_interval
        self.max_register_retries = max_register_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self._client: SignedHTTPClient | None = None
        self._task: asyncio.Task | None = None

    def _get_client(self) -> SignedHTTPClient:
        if not self._client:
            self._client = SignedHTTPClient(self.service_name)
        return self._client

    async def _register_one(self, card, agent_class) -> bool:
        """注册单个 agent;返 True 表示成功。"""
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
            return True
        except Exception as e:
            logger.debug("register attempt failed for %s: %s", card.agent_id, e)
            return False

    async def register_all(self, registry: AgentRegistry) -> None:
        """注册本服务所有 agent(单次,失败不重试;start() 负责重试)。"""
        for agent_class in registry.all():
            card = agent_class.to_card(self.service_name)
            await self._register_one(card, agent_class)

    async def register_all_with_retry(self, registry: AgentRegistry) -> None:
        """注册本服务所有 agent(指数退避,最多 max_register_retries 次)。

        任意一个 agent 注册成功就记 info;全部失败记 warning 但不 raise(让 lifespan 继续)。
        """
        backoff = self.initial_backoff
        for attempt in range(1, self.max_register_retries + 1):
            success = 0
            total = 0
            for agent_class in registry.all():
                total += 1
                card = agent_class.to_card(self.service_name)
                if await self._register_one(card, agent_class):
                    success += 1
            if success == total and total > 0:
                logger.info(
                    "All %d agents registered with orchestrator on attempt %d",
                    total, attempt,
                )
                return
            logger.warning(
                "Register attempt %d/%d: %d/%d succeeded, retrying in %.1fs",
                attempt, self.max_register_retries, success, total, backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.max_backoff)
        logger.warning(
            "Failed to register all agents after %d attempts; will keep heartbeating",
            self.max_register_retries,
        )

    async def heartbeat_loop(self, registry: AgentRegistry) -> None:
        """持续心跳(每 N 秒)。

        心跳失败时也会重新尝试 register(以防 orchestrator 重启后清空 registry)。
        """
        consecutive_failures = 0
        while True:
            try:
                all_ok = True
                for agent_class in registry.all():
                    # 心跳只关心 service + agent_id + version;不传 endpoint。
                    card = agent_class.to_card(self.service_name)
                    try:
                        r = await self._get_client().post(
                            f"{self.orchestrator_url}/internal/orchestrator/agents/{card.agent_id}/heartbeat",
                            timeout=5.0,
                        )
                        r.raise_for_status()
                    except Exception as e:
                        # 404 通常意味着 orchestrator 重启了 registry;下一轮 re-register
                        all_ok = False
                        logger.debug("Heartbeat for %s failed: %s", card.agent_id, e)
                if not all_ok:
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        # 连续失败 → 重新注册
                        logger.info("Re-registering agents after %d heartbeat failures",
                                    consecutive_failures)
                        await self.register_all(registry)
                        consecutive_failures = 0
                else:
                    consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Heartbeat loop iteration failed: %s", e)
            await asyncio.sleep(self.heartbeat_interval)

    def start(self, registry: AgentRegistry) -> None:
        """启动后台注册 + 心跳。"""

        async def _runner() -> None:
            try:
                await self.register_all_with_retry(registry)
            except Exception as e:
                logger.warning("register_all_with_retry crashed: %s", e)
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
