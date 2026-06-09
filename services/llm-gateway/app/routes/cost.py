"""成本查询 + 告警阈值(详见 v2 plan §12 + §Phase B Task 16)。

- GET  /api/cost/summary       → 今日/本周/本月/本年累计
- GET  /api/cost/daily         → 每日折线
- GET  /api/cost/by-book       → 按书拆分
- GET  /api/cost/recent-calls  → 最近 N 次调用
- PUT  /api/cost/thresholds    → 改告警阈值
"""
import json

from fastapi import APIRouter, Depends
from minbook_common.middleware import verify_user_token
from pydantic import BaseModel

from ..db import acquire

router = APIRouter()


@router.get("/summary")
async def cost_summary(user=Depends(verify_user_token)):
    """今日 / 本周 / 本月 / 本年累计。"""
    async with acquire() as conn:
        today = await conn.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd), 0) "
            "FROM llm.cost_rollup_day WHERE day = CURRENT_DATE"
        )
        week = await conn.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd), 0) FROM llm.cost_rollup_day "
            "WHERE day >= date_trunc('week', CURRENT_DATE)"
        )
        month = await conn.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd), 0) FROM llm.cost_rollup_day "
            "WHERE day >= date_trunc('month', CURRENT_DATE)"
        )
        year = await conn.fetchval(
            "SELECT COALESCE(SUM(total_cost_usd), 0) FROM llm.cost_rollup_day "
            "WHERE day >= date_trunc('year', CURRENT_DATE)"
        )
    return {
        "today": float(today or 0),
        "this_week": float(week or 0),
        "this_month": float(month or 0),
        "this_year": float(year or 0),
    }


@router.get("/daily")
async def daily_costs(days: int = 30, user=Depends(verify_user_token)):
    """每日折线。"""
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT day, total_cost_usd, call_count
               FROM llm.cost_rollup_day
               WHERE day >= CURRENT_DATE - $1::int
               ORDER BY day""",
            days,
        )
    return [
        {
            "day": str(r["day"]),
            "cost": float(r["total_cost_usd"]),
            "calls": r["call_count"],
        }
        for r in rows
    ]


@router.get("/by-book")
async def by_book(limit: int = 20, user=Depends(verify_user_token)):
    """按书拆分(最近 30 天)。"""
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT b.id, b.title, COALESCE(SUM(c.cost_estimate), 0) AS cost
               FROM llm.llm_calls c
               JOIN shared.books b ON c.book_id = b.id
               WHERE c.created_at > NOW() - INTERVAL '30 days'
               GROUP BY b.id, b.title
               ORDER BY cost DESC LIMIT $1""",
            limit,
        )
    return [
        {"book_id": str(r["id"]), "title": r["title"], "cost": float(r["cost"])}
        for r in rows
    ]


@router.get("/recent-calls")
async def recent_calls(limit: int = 50, user=Depends(verify_user_token)):
    """最近 N 次调用。"""
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT created_at, provider, model, agent_id, book_id,
                      prompt_tokens, completion_tokens, cost_estimate,
                      latency_ms, success
               FROM llm.llm_calls ORDER BY created_at DESC LIMIT $1""",
            limit,
        )
    return [dict(r) for r in rows]


class ThresholdUpdate(BaseModel):
    daily_usd: float
    monthly_usd: float
    per_book_usd: float
    spike_multiplier: float


@router.put("/thresholds")
async def update_thresholds(body: ThresholdUpdate, user=Depends(verify_user_token)):
    """改告警阈值(详见 §12 §3.1)。"""
    async with acquire() as conn:
        for key, val in [
            ("llm_cost_alert_daily_usd", body.daily_usd),
            ("llm_cost_alert_monthly_usd", body.monthly_usd),
            ("llm_cost_alert_per_book_usd", body.per_book_usd),
            ("llm_cost_alert_spike_multiplier", body.spike_multiplier),
        ]:
            await conn.execute(
                """UPDATE shared.global_config
                   SET config_value = $1::jsonb, updated_at = NOW()
                   WHERE config_key = $2""",
                json.dumps({"value": val}),
                key,
            )
    return {"status": "ok"}
