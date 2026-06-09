"""RadarAgent:市场趋势扫描(详见 v2 §1.2)。

通常由 NATS 周期事件 `minbook.reviewer.radar.scan.trigger` 触发,
不在 Pipeline Run 同步调用。本期实现:
1. 调 LLM(或使用启发式 / 第三方 API 占位)产出 trends
2. 缓存到 reviewer.radar_cache(失败优雅降级)
3. 发 NATS 事件 `minbook.reviewer.radar.scan.completed`

返:
  {
    "trends": [{"topic": "...", "heat": 0.0-1.0, "source": "..."}],
    "cache_id": "<uuid>" | None,
    "published": bool,
    "error": str | None
  }
"""
from __future__ import annotations

import json
import logging
import os
from uuid import UUID

from minbook_common.agents.base import (
    AgentInput,
    AgentOutput,
    BaseAgent,
)
from minbook_common.agents.registry import register_agent
from minbook_common.models import LLMChatRequest

log = logging.getLogger(__name__)


# Radar 事件 subject
EVENT_SCAN_COMPLETED = "minbook.reviewer.radar.scan.completed"
EVENT_SCAN_TRIGGER = "minbook.reviewer.radar.scan.trigger"


@register_agent
class RadarAgent(BaseAgent):
    name = "RadarAgent"
    version = "1.0.0"
    capabilities = ["trend_scanning", "market_signals"]
    memory_layers = ["episodic"]  # 扫描结果缓存

    async def run(self, input: AgentInput) -> AgentOutput:
        genre = input.book_settings.get("genre", "general")
        platform = input.book_settings.get("platform", "all")
        top_n = int(input.book_settings.get("top_n", 10))

        # 1. 调 LLM 抽取趋势(本期主要路径)
        trends: list[dict] = []
        llm_metrics: dict = {}
        try:
            prompt = self.prompts.render(
                "radar.j2",
                genre=genre,
                platform=platform,
                top_n=top_n,
            )
            response = await self.llm.chat(
                LLMChatRequest(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000,
                ),
                book_id=input.book_id,
                pipeline_run_id=input.pipeline_run_id,
                node_id=input.node_id,
                agent_id=self.name,
            )
            llm_metrics = {
                "tokens": response.usage,
                "cost_usd": float(response.cost_usd),
                "latency_ms": response.latency_ms,
            }
            try:
                data = json.loads(response.content)
                if isinstance(data, dict) and isinstance(data.get("trends"), list):
                    trends = data["trends"]
                elif isinstance(data, list):
                    trends = data
            except Exception as e:  # noqa: BLE001
                log.warning("RadarAgent: JSON parse failed: %s", e)
        except Exception as e:  # noqa: BLE001
            log.warning("RadarAgent: LLM scan failed: %s", e)

        # 2. fallback:空趋势也允许(可接第三方 API 扩展)
        if not trends:
            trends = [
                {
                    "topic": f"{genre}热门设定",
                    "heat": 0.5,
                    "source": "fallback",
                    "note": "LLM scan unavailable, returning placeholder",
                },
            ]

        # 3. 缓存到 reviewer.radar_cache(失败优雅降级)
        cache_id: str | None = None
        try:
            pool = self.memory.pool
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO reviewer.radar_cache
                       (book_id, genre, platform, trends_json)
                       VALUES ($1, $2, $3, $4)
                       RETURNING id""",
                    input.book_id,
                    genre,
                    platform,
                    json.dumps(trends),
                )
                if row and "id" in row:
                    cache_id = str(row["id"])
        except Exception as e:  # noqa: BLE001
            log.warning("RadarAgent: radar_cache insert failed: %s", e)

        # 4. 发 NATS 事件(失败优雅降级)
        published = False
        publish_error: str | None = None
        try:
            await self._publish_completed(
                book_id=input.book_id,
                genre=genre,
                platform=platform,
                trends_count=len(trends),
                cache_id=cache_id,
            )
            published = True
        except Exception as e:  # noqa: BLE001
            log.warning("RadarAgent: NATS publish failed: %s", e)
            publish_error = str(e)

        return AgentOutput(
            status="ok" if trends else "warning",
            result={
                "trends": trends,
                "trend_count": len(trends),
                "cache_id": cache_id,
                "published": published,
                "publish_error": publish_error,
                "genre": genre,
                "platform": platform,
            },
            metrics=llm_metrics,
        )

    async def _publish_completed(
        self,
        book_id: UUID,
        genre: str,
        platform: str,
        trends_count: int,
        cache_id: str | None,
    ) -> None:
        """发布 NATS 事件。失败由调用方捕获。"""
        from minbook_common.nats_client import MinBookNATS

        nats_url = os.environ.get("NATS_URL", "nats://nats:4222")
        nc = MinBookNATS(
            url=nats_url,
            service_name="agent-reviewer-service",
            service_version="0.3.0",
        )
        try:
            await nc.connect()
            try:
                await nc.publish_event(
                    subject=EVENT_SCAN_COMPLETED,
                    data={
                        "book_id": str(book_id),
                        "genre": genre,
                        "platform": platform,
                        "trends_count": trends_count,
                        "cache_id": cache_id,
                    },
                )
            finally:
                await nc.close()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"NATS publish failed: {e}") from e
