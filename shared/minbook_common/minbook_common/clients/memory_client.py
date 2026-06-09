"""Agent 私有记忆客户端(详见 v2 §2.5)。

每个 agent 服务用自己的 PG user(svc_planner / svc_writer / svc_reviewer),只读写自己 schema 的表:
- {schema}.episodes:episodic + semantic 记忆(vector 索引)
- {schema}.prompt_templates:procedural 记忆(模板)
- {schema}.style_corpus:(writer 专用)文风语料
- {schema}.audit_history:(reviewer 专用)审计历史

embed 走 llm-gateway /internal/llm/embed 端点;若 OPENAI_API_KEY 没设,_embed 走 None fallback
(让 agent 容器不 crash,但 episodic 检索会降级)。
"""
import json
import logging
import os
from typing import Any
from uuid import UUID

import asyncpg
import httpx

log = logging.getLogger(__name__)


class MemoryClient:
    """每个 agent 服务用自己的 PG user,只能读写自己 schema 的表。"""

    def __init__(self, service: str, schema: str):
        """service: 'planner' | 'writer' | 'reviewer'
           schema:  对应 PG schema(planner / writer / reviewer)
        """
        self.service = service
        self.schema = schema
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            user=f"svc_{self.service}",
            password=os.environ.get(
                f"POSTGRES_{self.service.upper()}_PASSWORD", "minbook_dev",
            ),
            database=os.environ.get("POSTGRES_DB", "minbook"),
            min_size=2,
            max_size=10,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("MemoryClient.init() not called")
        return self._pool

    async def recall(
        self,
        book_id: UUID,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        """向量检索 episodic 记忆(走 pgvector cosine 距离)。"""
        # 1. 拿 query embedding
        query_emb = await self._embed(query)
        if query_emb is None:
            # 无 embed 服务时降级:返回空列表
            log.warning("MemoryClient.recall: embed unavailable, returning []")
            return []

        # 2. PG pgvector 查询
        sql = f"""
            SELECT id, intent_json AS content, created_at,
                   1 - (embedding <=> $1::vector) AS score
            FROM {self.schema}.episodes
            WHERE book_id = $2 AND archived_at IS NULL
        """
        params: list[Any] = [query_emb, book_id]
        if filters and "chapter_number" in filters:
            sql += " AND chapter_number = $3"
            params.append(filters["chapter_number"])
        sql += " ORDER BY embedding <=> $1::vector LIMIT $4"
        params.append(top_k)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [
            {
                "id": str(r["id"]),
                "content": r["content"],
                "score": float(r["score"]),
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]

    async def store_episode(
        self,
        book_id: UUID,
        episode: dict,
        embedding: list[float] | None = None,
    ) -> str:
        """存储 episodic。"""
        if embedding is None:
            text = json.dumps(episode, ensure_ascii=False)
            embedding = await self._embed(text)

        if embedding is None:
            # 降级:不写 vector(用 NULL),后续 recall 不会命中这条
            log.warning("MemoryClient.store_episode: embed unavailable, storing without vector")
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""INSERT INTO {self.schema}.episodes
                       (book_id, intent_json) VALUES ($1, $2) RETURNING id""",
                    book_id, json.dumps(episode),
                )
            return str(row["id"])

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""INSERT INTO {self.schema}.episodes
                   (book_id, intent_json, embedding) VALUES ($1, $2, $3::vector)
                   RETURNING id""",
                book_id, json.dumps(episode), embedding,
            )
        return str(row["id"])

    async def load_procedural(self, template_name: str) -> str | None:
        """加载 procedural 记忆(prompt 模板,从 prompt_templates 表读)。"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT template_content FROM {self.schema}.prompt_templates
                   WHERE template_name = $1 AND is_active = true
                   ORDER BY version DESC LIMIT 1""",
                template_name,
            )
        return row["template_content"] if row else None

    async def _embed(self, text: str) -> list[float] | None:
        """调 llm-gateway 拿 embedding(走 OpenAI text-embedding-3-small 兼容协议)。

        返回 None 表示 embed 服务不可用(无 OPENAI_API_KEY / provider 503),
        caller 应降级处理(不 crash)。
        """
        llm_url = os.environ.get("LLM_GATEWAY_URL", "http://llm-gateway:8006")
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{llm_url}/internal/llm/embed",
                    json={
                        "model": "text-embedding-3-small",
                        "input": text,
                        "provider": "openai",
                    },
                    timeout=30.0,
                )
                r.raise_for_status()
                data = r.json()
                emb = data.get("embedding")
                if isinstance(emb, list):
                    return emb
                log.warning("MemoryClient._embed: unexpected response shape: %s", data)
                return None
        except Exception as e:
            # 优雅降级:不 crash,callers 收到 None
            log.warning("MemoryClient._embed failed: %s", e)
            return None
