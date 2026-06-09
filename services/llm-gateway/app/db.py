"""DB 连接 + 成本估算(详见 v2 plan §Phase B Task 15)。

- asyncpg 连接池(默认 2~10 连接)
- fetch_provider_cost:从 llm.llm_providers 表读定价,计算成本
- record_llm_call:写一行 llm.llm_calls 表
"""
import os
from contextlib import asynccontextmanager
from decimal import Decimal

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        user=os.environ.get("POSTGRES_USER", "minbook"),
        password=os.environ.get("POSTGRES_PASSWORD", "minbook_dev"),
        database=os.environ.get("POSTGRES_DB", "minbook"),
        min_size=2,
        max_size=10,
    )


async def close_db():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def acquire():
    if _pool is None:
        raise RuntimeError("DB pool not initialized; call init_db() first")
    async with _pool.acquire() as conn:
        yield conn


async def fetch_provider_cost(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> Decimal:
    """从 llm.llm_providers 表读定价,计算成本(详见 §12 §1.3)。

    未知模型返 0(不阻断调用)。
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT cost_per_1k_input_tokens, cost_per_1k_output_tokens
               FROM llm.llm_providers
               WHERE provider = $1 AND model = $2
                 AND effective_from <= CURRENT_DATE
               ORDER BY effective_from DESC LIMIT 1""",
            provider,
            model,
        )
    if not row:
        return Decimal(0)
    return (
        Decimal(prompt_tokens) / 1000 * Decimal(row["cost_per_1k_input_tokens"])
        + Decimal(completion_tokens) / 1000 * Decimal(row["cost_per_1k_output_tokens"])
    )


async def record_llm_call(
    *,
    book_id,
    pipeline_run_id,
    task_id,
    agent_id,
    node_id,
    provider: str,
    model: str,
    endpoint,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    cost_estimate,
    success: bool,
    error_type,
    trace_id,
):
    """写一行 llm.llm_calls(详见 §12 §1.2)。

    所有调用都是异步 fire-and-forget;失败不抛(避免污染主流程)。
    """
    try:
        async with acquire() as conn:
            await conn.execute(
                """INSERT INTO llm.llm_calls
                   (book_id, pipeline_run_id, task_id, agent_id, node_id,
                    provider, model, endpoint, prompt_tokens, completion_tokens,
                    latency_ms, cost_estimate, success, error_type, trace_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                           $11, $12, $13, $14, $15)""",
                book_id,
                pipeline_run_id,
                task_id,
                agent_id,
                node_id,
                provider,
                model,
                endpoint,
                prompt_tokens,
                completion_tokens,
                latency_ms,
                cost_estimate,
                success,
                error_type,
                trace_id,
            )
    except Exception:
        # fire-and-forget:不阻断主流程
        pass
